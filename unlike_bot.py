# Instagram Mass Unlike Bot
# Copyright (C) 2026 mehmet-ak
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Instagram Mass Unlike Bot.

A Tkinter wizard that removes your likes from Instagram posts and Reels. It reads
the ``liked_posts.json`` file from Instagram's data export and uses a Chrome window,
controlled through Selenium, to unlike each post.

The file is organised top to bottom as follows:

1. Settings and translations
2. Reading the Instagram export (pure functions, no UI)
3. Progress storage
4. Starting Chrome
5. The unlike routine (``UnlikeSession``, no UI)
6. The Tkinter wizard
"""

from __future__ import annotations

import json
import logging
import random
import re
import sys
import threading
import tkinter as tk
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable, Iterable
from urllib.parse import urlparse

import undetected_chromedriver as uc
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

logger = logging.getLogger("unlike_bot")

# ---------------------------------------------------------------------------
# 1. Settings and translations
# ---------------------------------------------------------------------------

INSTAGRAM_URL = "https://www.instagram.com/"

# Window and branding
WINDOW_WIDTH = 550
WINDOW_HEIGHT = 520
WRAP_LENGTH = 480  # long texts wrap at this width (pixels) so they stay centred
ICON_FILE = "assets/icon.png"  # bundled into the executable, see README
WINDOW_CLASS = "InstagramMassUnlike"  # lets Linux desktops match the window to its launcher

# Pacing. These delays exist to reduce the risk of an Instagram "Action Block".
# Lowering them is strongly discouraged. All values are in seconds.
PAGE_LOAD_DELAY = (4.0, 7.0)  # let a post page finish loading
PRE_CLICK_DELAY = (1.0, 2.5)  # pause before clicking the heart
POST_INTERVAL = (15.0, 25.0)  # wait between two posts
LONG_BREAK_EVERY = 35  # take a long break after this many successful unlikes...
LONG_BREAK_SECONDS = 300  # ...lasting this long
ELEMENT_TIMEOUT = 5  # how long to wait for the heart button to appear or change

# Stop when this many posts in a row cannot be verified. That usually means the
# user is logged out, Instagram changed its page, or an Action Block is active.
MAX_CONSECUTIVE_FAILURES = 5

# Instagram labels the heart icon according to the account language. Only these
# languages are supported.
UNLIKE_LABELS = ("Unlike", "Beğenmekten Vazgeç")  # shown on a post you have liked
LIKE_LABELS = ("Like", "Beğen")  # shown on a post you have not liked


def _heart_button_xpath(labels: Iterable[str]) -> str:
    """Build an XPath that finds the clickable heart button for the given labels."""
    condition = " or ".join(f"@aria-label='{label}'" for label in labels)
    return f"//*[local-name()='svg' and ({condition})]/ancestor::div[@role='button']"


def resource_path(relative_path: str) -> Path:
    """Locate a bundled data file, both from source and inside a PyInstaller executable."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / relative_path


UNLIKE_BUTTON_XPATH = _heart_button_xpath(UNLIKE_LABELS)
LIKE_BUTTON_XPATH = _heart_button_xpath(LIKE_LABELS)

TRANSLATIONS: dict[str, dict[str, str]] = {
    "tr": {
        "title": "Instagram Toplu Beğeni Silici",
        "next": "İleri >",
        "back": "< Geri",
        "browse": "Gözat...",
        "error_title": "Hata",
        "info_title": "Bilgi",
        "confirm_title": "Onay",
        "done_title": "Bitti",
        "chrome_error_title": "Chrome Hatası",
        "step2_title": "2. İstisna (Whitelist) Ayarı",
        "whitelist_question": (
            "İstisna (Whitelist) kullanmak istiyor musunuz?\n"
            "(Takip ettiklerinizin beğenileri silinmez)"
        ),
        "yes": "Evet, kullan",
        "no": "Hayır, herkesi sil",
        "whitelist_select": (
            "Takipçi ve/veya takip edilen JSON dosyalarını ekleyin "
            "(birden fazla ekleyebilirsiniz):"
        ),
        "add_files": "Dosya ekle...",
        "remove_selected": "Seçileni kaldır",
        "whitelist_item": "{name}  -  {count} kullanıcı adı",
        "whitelist_total": "Korunan kullanıcı adları (benzersiz): {count}",
        "whitelist_file_invalid": "'{name}' geçerli bir JSON dosyası değil veya bozuk.",
        "whitelist_file_empty": "'{name}' dosyasında kullanıcı adı bulunamadı.",
        "step3_title": "3. Beğeni Dosyası Seçimi",
        "likes_select": "Lütfen beğenilerin (liked_posts.json) dosyasını seçin:",
        "invalid_json": "Seçilen dosya geçerli bir JSON değil veya bozuk!",
        "invalid_structure": (
            "Bu dosya bir Instagram liked_posts.json dışa aktarımına benzemiyor."
        ),
        "stats": (
            "Toplam beğeni: {total}\n"
            "Korumaya alınan: {protected}\n"
            "Atlanan (okunamayan veya sahibi bilinmeyen): {skipped}\n"
            "Daha önce işlenen: {done}\n"
            "Şimdi silinecek: {targets}"
        ),
        "nothing_left": "Bu dosyadaki tüm beğeniler zaten işlenmiş!",
        "err_nofile": "Lütfen önce bir dosya seçin!",
        "err_notarget": "Silinecek hiçbir URL bulunamadı!",
        "step4_title": "4. Giriş ve Onay",
        "open_chrome": "1. Chrome'u Aç ve Giriş Yap",
        "ready_btn": "2. Hazırız! İşlemi Başlat",
        "login_warn": (
            "Tarayıcı açıldığında Instagram'a giriş yapın.\n"
            "Girişiniz tamamen bittikten sonra 2. butona tıklayın."
        ),
        "opening_chrome": "Chrome açılıyor...",
        "chrome_error": "Chrome başlatılamadı:\n{error}",
        "not_logged_in": (
            "Henüz Instagram'a giriş yapmamış görünüyorsunuz.\nYine de devam edilsin mi?"
        ),
        "step5_title": "5. İşlem Durumu",
        "status_init": "Başlatılıyor...",
        "status_loading": "Yükleniyor...",
        "status_working": "[{current}/{total}] İşleniyor: {post}",
        "status_wait": "Bot Koruması: {seconds} saniye bekleniyor...",
        "status_long_wait": "UZUN MOLA: Spam koruması için 5 dk bekleniyor...",
        "counters": (
            "Kaldırılan: {unliked}  |  Zaten kaldırılmış: {already}  |  "
            "Doğrulanamayan: {unverified}"
        ),
        "stop": "Durdur",
        "stopping": "Mevcut adımdan sonra durduruluyor...",
        "summary_finished": "İşlem tamamlandı!",
        "summary_stopped": "Kullanıcı tarafından durduruldu.",
        "summary_too_many_failures": (
            "Durduruldu: art arda {limit} gönderi doğrulanamadı.\n"
            "Oturumunuz kapanmış olabilir veya Instagram işlemleri engelliyor olabilir. "
            "Tarayıcıyı kontrol edin, bir süre bekleyin ve tekrar deneyin."
        ),
        "summary_browser_closed": "Durduruldu: Chrome penceresi kapatıldı.",
        "summary_counts": (
            "Kaldırılan: {unliked}\n"
            "Zaten kaldırılmış: {already}\n"
            "Doğrulanamayan: {unverified}"
        ),
        "summary_hint": (
            "Doğrulanamayan beğeniler sonraki çalıştırma için saklandı. "
            "Aracı aynı beğeni dosyasıyla tekrar başlatabilirsiniz."
        ),
        "unexpected_error": "Beklenmeyen bir hata oluştu. Ayrıntılar .log dosyasında.",
        "confirm_quit": "Bot hâlâ çalışıyor. Durdurup çıkmak istiyor musunuz?",
    },
    "en": {
        "title": "Instagram Mass Unlike Bot",
        "next": "Next >",
        "back": "< Back",
        "browse": "Browse...",
        "error_title": "Error",
        "info_title": "Info",
        "confirm_title": "Confirm",
        "done_title": "Finished",
        "chrome_error_title": "Chrome Error",
        "step2_title": "2. Whitelist Settings",
        "whitelist_question": (
            "Do you want to use a whitelist?\n(Keep likes of people you follow)"
        ),
        "yes": "Yes, use whitelist",
        "no": "No, target everyone",
        "whitelist_select": (
            "Add your followers and/or following JSON files (you can add several):"
        ),
        "add_files": "Add file(s)...",
        "remove_selected": "Remove selected",
        "whitelist_item": "{name}  -  {count} usernames",
        "whitelist_total": "Protected usernames (unique): {count}",
        "whitelist_file_invalid": "'{name}' is not a valid JSON file or is corrupted.",
        "whitelist_file_empty": "No usernames were found in '{name}'.",
        "step3_title": "3. Select Likes File",
        "likes_select": "Please select your likes (liked_posts.json) file:",
        "invalid_json": "Selected file is not a valid JSON or corrupted!",
        "invalid_structure": "This file does not look like an Instagram liked_posts.json export.",
        "stats": (
            "Total likes: {total}\n"
            "Protected (whitelist): {protected}\n"
            "Skipped (unreadable or unknown owner): {skipped}\n"
            "Already done earlier: {done}\n"
            "To unlike now: {targets}"
        ),
        "nothing_left": "Everything in this file has already been processed!",
        "err_nofile": "Please select a file first!",
        "err_notarget": "No URLs found to unlike!",
        "step4_title": "4. Login & Confirm",
        "open_chrome": "1. Open Chrome & Login",
        "ready_btn": "2. Ready! Start Process",
        "login_warn": (
            "When the browser opens, log in to Instagram.\n"
            "Click the 2nd button ONLY after you are fully logged in."
        ),
        "opening_chrome": "Opening Chrome...",
        "chrome_error": "Could not start Chrome:\n{error}",
        "not_logged_in": (
            "You do not seem to be logged in to Instagram yet.\nContinue anyway?"
        ),
        "step5_title": "5. Progress Status",
        "status_init": "Starting...",
        "status_loading": "Loading...",
        "status_working": "[{current}/{total}] Processing: {post}",
        "status_wait": "Bot Protection: Waiting {seconds} seconds...",
        "status_long_wait": "LONG BREAK: Waiting 5 mins to avoid spam filter...",
        "counters": (
            "Unliked: {unliked}  |  Already unliked: {already}  |  "
            "Could not verify: {unverified}"
        ),
        "stop": "Stop",
        "stopping": "Stopping after the current step...",
        "summary_finished": "All done!",
        "summary_stopped": "Stopped by user.",
        "summary_too_many_failures": (
            "Stopped: {limit} posts in a row could not be verified.\n"
            "You may be logged out, or Instagram may be blocking actions. "
            "Check the browser, wait a while, then try again."
        ),
        "summary_browser_closed": "Stopped: the Chrome window was closed.",
        "summary_counts": (
            "Unliked: {unliked}\nAlready unliked: {already}\nCould not verify: {unverified}"
        ),
        "summary_hint": (
            "Posts that could not be verified were kept for the next run. "
            "Start the tool again with the same likes file to retry them."
        ),
        "unexpected_error": "An unexpected error occurred. See the .log file for details.",
        "confirm_quit": "The bot is still running. Stop it and quit?",
    },
}

# ---------------------------------------------------------------------------
# 2. Reading the Instagram export
# ---------------------------------------------------------------------------


class InvalidExportError(ValueError):
    """Raised when a JSON file does not have the structure of a liked_posts.json export."""


@dataclass(frozen=True)
class LikedPost:
    """A post or Reel from the export. ``owner`` is None if it cannot be read."""

    url: str
    owner: str | None = None

    @property
    def short_id(self) -> str:
        """The last part of the URL, e.g. the shortcode of a post."""
        path = urlparse(self.url).path.strip("/")
        return path.split("/")[-1] if path else self.url


def load_json_file(path: str | Path) -> Any:
    """Read and parse a UTF-8 JSON file."""
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def collect_usernames(node: Any, usernames: set[str] | None = None) -> set[str]:
    """Recursively collect every username in a followers/following export, in lower case.

    Instagram uses two layouts for these files:

    * ``followers_1.json``: the username is the ``value`` of a ``string_list_data`` entry.
    * ``following.json``: the username is the ``title`` of the entry, and
      ``string_list_data`` only holds the profile link and a timestamp.
    """
    if usernames is None:
        usernames = set()
    if isinstance(node, dict):
        entries = node.get("string_list_data")
        if isinstance(entries, list):
            title = node.get("title")
            if isinstance(title, str) and title.strip():
                usernames.add(title.strip().lower())
            for entry in entries:
                value = entry.get("value") if isinstance(entry, dict) else None
                if isinstance(value, str) and value.strip():
                    usernames.add(value.strip().lower())
        for child in node.values():
            collect_usernames(child, usernames)
    elif isinstance(node, list):
        for child in node:
            collect_usernames(child, usernames)
    return usernames


def read_whitelist_usernames(path: str | Path) -> set[str]:
    """Usernames from one followers/following file (raises OSError or ValueError if unreadable)."""
    return collect_usernames(load_json_file(path))


def merge_usernames(username_sets: Iterable[set[str]]) -> set[str]:
    """Combine the usernames of several whitelist files into one set without duplicates."""
    merged: set[str] = set()
    for usernames in username_sets:
        merged |= usernames
    return merged


def parse_liked_posts(data: Any) -> tuple[list[LikedPost], int]:
    """Turn the parsed liked_posts.json into posts.

    Returns ``(posts, unreadable)`` where ``unreadable`` counts entries without a URL.
    Raises InvalidExportError if the top level is not a list.
    """
    if not isinstance(data, list):
        raise InvalidExportError("Expected a list of liked posts at the top level.")
    posts: list[LikedPost] = []
    unreadable = 0
    for item in data:
        post = _parse_liked_item(item)
        if post is None:
            unreadable += 1
        else:
            posts.append(post)
    return posts, unreadable


def _parse_liked_item(item: Any) -> LikedPost | None:
    """Read the URL and owner username of one entry; None if it has no URL."""
    if not isinstance(item, dict):
        return None
    labels = item.get("label_values")
    if not isinstance(labels, list):
        return None
    url = ""
    owner = None
    for label in labels:
        if not isinstance(label, dict):
            continue
        if "href" in label:
            url = label.get("href") or ""
        title = str(label.get("title", ""))
        if "Owner" in title or "Sahibi" in title:  # English / Turkish export
            owner = _find_owner_username(label) or owner
    return LikedPost(url=url, owner=owner) if url else None


def _find_owner_username(owner_label: dict) -> str | None:
    """Find the username inside the nested "Owner" block of an export entry."""
    username = None
    for owner_item in owner_label.get("dict", []):
        if not isinstance(owner_item, dict):
            continue
        for prop in owner_item.get("dict", []):
            if not isinstance(prop, dict):
                continue
            prop_label = str(prop.get("label", ""))
            if "Username" in prop_label or "Kullan" in prop_label:  # English / Turkish
                username = prop.get("value")
    return username if isinstance(username, str) and username else None


def select_targets(
    posts: list[LikedPost], whitelist: set[str] | None
) -> tuple[list[LikedPost], int, int]:
    """Decide which posts to unlike.

    ``whitelist`` is a set of lower-case usernames whose posts must keep their like,
    or None/empty to unlike everything. Returns ``(targets, protected, unknown_owner)``.
    When a whitelist is used, posts whose owner is unknown are skipped to be safe.
    """
    if not whitelist:
        return list(posts), 0, 0
    targets: list[LikedPost] = []
    protected = 0
    unknown_owner = 0
    for post in posts:
        if post.owner is None:
            unknown_owner += 1
        elif post.owner.lower() in whitelist:
            protected += 1
        else:
            targets.append(post)
    return targets, protected, unknown_owner


# ---------------------------------------------------------------------------
# 3. Progress storage
# ---------------------------------------------------------------------------


class ProgressStore:
    """Remembers finished posts in a side file, so the user's export is never modified.

    The side file sits next to the likes file (``liked_posts.progress.jsonl``) and
    holds one JSON object per line. Appending a line is cheap and a crash can at
    worst damage the last line, which is ignored when loading.
    """

    SUFFIX = ".progress.jsonl"

    def __init__(self, likes_file: str | Path) -> None:
        likes_file = Path(likes_file)
        self.path = likes_file.with_name(likes_file.stem + self.SUFFIX)

    def load_done_urls(self) -> set[str]:
        """Return the URLs that were finished in earlier runs."""
        done: set[str] = set()
        if not self.path.exists():
            return done
        with open(self.path, "r", encoding="utf-8") as file:
            for line in file:
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue  # e.g. a half-written last line after a crash
                url = record.get("url") if isinstance(record, dict) else None
                if isinstance(url, str):
                    done.add(url)
        return done

    def mark_done(self, url: str, status: str) -> None:
        """Record that a post is finished (unliked or already unliked)."""
        line = json.dumps({"url": url, "status": status}, ensure_ascii=False)
        with open(self.path, "a", encoding="utf-8") as file:
            file.write(line + "\n")


# ---------------------------------------------------------------------------
# 4. Starting Chrome
# ---------------------------------------------------------------------------

# Selenium reports the installed version like this: "Current browser version is 156.0.8078.79"
CHROME_VERSION_PATTERN = re.compile(r"Current browser version is (\d+)")


def start_chrome() -> Any:
    """Start Chrome through undetected-chromedriver and return the driver.

    undetected-chromedriver downloads the newest ChromeDriver by default. That fails
    whenever the installed Chrome is a major version behind ("This version of
    ChromeDriver only supports Chrome version 157 ... Current browser version is 156").
    In that case we read the installed version from the error and retry with the
    matching driver.
    """
    try:
        return uc.Chrome(options=uc.ChromeOptions())
    except WebDriverException as error:
        match = CHROME_VERSION_PATTERN.search(str(error))
        if match is None:
            raise
        installed_version = int(match.group(1))
        logger.info("ChromeDriver mismatch, retrying for Chrome %s", installed_version)
        # A ChromeOptions object cannot be reused, so build a fresh one.
        return uc.Chrome(options=uc.ChromeOptions(), version_main=installed_version)


def short_error_message(error: BaseException) -> str:
    """The readable part of a Selenium error, without the long stack trace."""
    return str(error).split("Stacktrace:")[0].strip()


# ---------------------------------------------------------------------------
# 5. The unlike routine
# ---------------------------------------------------------------------------


class PostStatus(Enum):
    """Result of processing one post."""

    UNLIKED = "unliked"  # clicked, and the heart was seen flipping back
    ALREADY_UNLIKED = "already_unliked"  # the page shows a "Like" heart: nothing to do
    UNVERIFIED = "unverified"  # state unclear (logged out, blocked, changed page...)
    ERROR = "error"  # the browser raised an error


class StopReason(Enum):
    """Why a session ended."""

    FINISHED = "finished"
    STOPPED = "stopped"
    TOO_MANY_FAILURES = "too_many_failures"
    BROWSER_CLOSED = "browser_closed"


@dataclass
class SessionSummary:
    """Counters for one session. ``unverified`` includes browser errors."""

    reason: StopReason = StopReason.FINISHED
    unliked: int = 0
    already_unliked: int = 0
    unverified: int = 0


@dataclass(frozen=True)
class ProgressUpdate:
    """What the UI needs to show while the session runs."""

    current: int  # posts handled so far
    total: int
    post: LikedPost
    status: str  # a translation key such as "status_loading"
    seconds: float = 0.0  # used by "status_wait"
    unliked: int = 0
    already_unliked: int = 0
    unverified: int = 0


class StopRequested(Exception):
    """Raised inside a session when the user asked to stop."""


class UnlikeSession:
    """Unlikes a list of posts through an already logged-in browser.

    The session never touches the user interface: it reports progress through the
    ``on_progress`` callback and can be stopped with ``stop_event``.
    """

    def __init__(
        self,
        driver: Any,
        targets: list[LikedPost],
        store: ProgressStore,
        stop_event: threading.Event,
        on_progress: Callable[[ProgressUpdate], None],
    ) -> None:
        self.driver = driver
        self.targets = targets
        self.store = store
        self.stop_event = stop_event
        self.on_progress = on_progress
        self.summary = SessionSummary()

    def run(self) -> SessionSummary:
        """Process every target. Always returns a summary, even when stopped early."""
        total = len(self.targets)
        consecutive_failures = 0
        try:
            for index, post in enumerate(self.targets):
                self._check_stop()
                self._report(index, total, post, "status_loading")
                status = self._process_post(post)

                if status is PostStatus.ERROR and not self._browser_is_alive():
                    self.summary.reason = StopReason.BROWSER_CLOSED
                    return self.summary

                self._record(post, status)
                if status in (PostStatus.UNLIKED, PostStatus.ALREADY_UNLIKED):
                    consecutive_failures = 0
                else:
                    consecutive_failures += 1
                    if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                        self.summary.reason = StopReason.TOO_MANY_FAILURES
                        return self.summary

                if index < total - 1:
                    self._pause_between_posts(index + 1, total, post, status)
        except StopRequested:
            self.summary.reason = StopReason.STOPPED
        return self.summary

    # -- per-post work -------------------------------------------------------

    def _process_post(self, post: LikedPost) -> PostStatus:
        """Open a post and unlike it, verifying the result."""
        try:
            self.driver.get(post.url)
            self._sleep(random.uniform(*PAGE_LOAD_DELAY))

            state = self._detect_like_state()
            if state == "not_liked":
                return PostStatus.ALREADY_UNLIKED
            if state is None:
                logger.warning("No heart button found on %s", post.url)
                return PostStatus.UNVERIFIED

            self._sleep(random.uniform(*PRE_CLICK_DELAY))
            self._click_unlike_button()
            if self._wait_until_unliked():
                return PostStatus.UNLIKED
            logger.warning("The heart did not change after clicking on %s", post.url)
            return PostStatus.UNVERIFIED
        except WebDriverException:
            logger.exception("Browser error while processing %s", post.url)
            return PostStatus.ERROR

    def _detect_like_state(self) -> str | None:
        """Return "liked", "not_liked", or None if no heart button shows up in time."""

        def probe(driver: Any) -> str | bool:
            if driver.find_elements(By.XPATH, UNLIKE_BUTTON_XPATH):
                return "liked"
            if driver.find_elements(By.XPATH, LIKE_BUTTON_XPATH):
                return "not_liked"
            return False

        try:
            return WebDriverWait(self.driver, ELEMENT_TIMEOUT).until(probe)
        except TimeoutException:
            return None

    def _click_unlike_button(self) -> None:
        """Click the heart: with a mouse-like action first, then with JavaScript."""
        button = self.driver.find_element(By.XPATH, UNLIKE_BUTTON_XPATH)
        try:
            ActionChains(self.driver).move_to_element(button).pause(
                random.uniform(0.3, 0.9)
            ).click().perform()
        except WebDriverException:
            self.driver.execute_script("arguments[0].click();", button)

    def _wait_until_unliked(self) -> bool:
        """True once the "Unlike" heart is gone and a "Like" heart is shown."""

        def verified(driver: Any) -> bool:
            return not driver.find_elements(By.XPATH, UNLIKE_BUTTON_XPATH) and bool(
                driver.find_elements(By.XPATH, LIKE_BUTTON_XPATH)
            )

        try:
            WebDriverWait(self.driver, ELEMENT_TIMEOUT).until(verified)
            return True
        except TimeoutException:
            return False

    def _browser_is_alive(self) -> bool:
        """True if the browser window can still be reached."""
        try:
            return bool(self.driver.window_handles)
        except Exception:  # noqa: BLE001 - any failure here means the browser is gone
            return False

    # -- bookkeeping and pacing ---------------------------------------------

    def _record(self, post: LikedPost, status: PostStatus) -> None:
        if status is PostStatus.UNLIKED:
            self.summary.unliked += 1
            self.store.mark_done(post.url, status.value)
        elif status is PostStatus.ALREADY_UNLIKED:
            self.summary.already_unliked += 1
            self.store.mark_done(post.url, status.value)
        else:
            self.summary.unverified += 1  # stays pending: it is retried on the next run

    def _pause_between_posts(
        self, current: int, total: int, post: LikedPost, status: PostStatus
    ) -> None:
        delay = random.uniform(*POST_INTERVAL)
        self._report(current, total, post, "status_wait", delay)
        self._sleep(delay)
        # Long break right after every LONG_BREAK_EVERY-th successful unlike only.
        if status is PostStatus.UNLIKED and self.summary.unliked % LONG_BREAK_EVERY == 0:
            self._report(current, total, post, "status_long_wait")
            self._sleep(LONG_BREAK_SECONDS)

    def _report(
        self, current: int, total: int, post: LikedPost, status: str, seconds: float = 0.0
    ) -> None:
        self.on_progress(
            ProgressUpdate(
                current=current,
                total=total,
                post=post,
                status=status,
                seconds=seconds,
                unliked=self.summary.unliked,
                already_unliked=self.summary.already_unliked,
                unverified=self.summary.unverified,
            )
        )

    def _check_stop(self) -> None:
        if self.stop_event.is_set():
            raise StopRequested

    def _sleep(self, seconds: float) -> None:
        """Sleep, but wake up immediately when the user asks to stop."""
        if self.stop_event.wait(seconds):
            raise StopRequested


# ---------------------------------------------------------------------------
# 6. The Tkinter wizard
# ---------------------------------------------------------------------------


class UnlikeWizard(tk.Tk):
    """Main window: shows one wizard step (frame) at a time and holds shared state."""

    def __init__(self) -> None:
        super().__init__(className=WINDOW_CLASS)
        self.title(TRANSLATIONS["en"]["title"])
        self.resizable(False, False)
        self._set_window_icon()
        self._center_on_screen()

        # State shared between the steps
        self.language = "en"
        self.use_whitelist = tk.BooleanVar(value=False)
        self.whitelist_sources: dict[str, set[str]] = {}  # file path -> usernames in that file
        self.likes_path = ""
        self.whitelist_usernames: set[str] = set()
        self.targets: list[LikedPost] = []
        self.progress_store: ProgressStore | None = None
        self.driver: Any = None
        self.stop_event = threading.Event()
        self.is_running = False

        container = ttk.Frame(self)
        container.pack(fill="both", expand=True)
        # Without these weights every step stays in the top-left corner of the window.
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        self.frames: dict[str, WizardFrame] = {}
        for frame_class in (LanguageFrame, WhitelistFrame, LikesFrame, LoginFrame, ProgressFrame):
            frame = frame_class(parent=container, controller=self)
            self.frames[frame_class.__name__] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.show_frame("LanguageFrame")

    def _set_window_icon(self) -> None:
        """Use assets/icon.png as the window icon (title bar and taskbar)."""
        try:
            # Keep a reference: Tk forgets the icon if the image object is garbage-collected.
            self.icon_image = tk.PhotoImage(file=str(resource_path(ICON_FILE)))
            self.iconphoto(True, self.icon_image)
        except tk.TclError:
            logger.debug("Could not load the window icon", exc_info=True)

    def _center_on_screen(self) -> None:
        """Open the window in the middle of the screen."""
        x = max((self.winfo_screenwidth() - WINDOW_WIDTH) // 2, 0)
        y = max((self.winfo_screenheight() - WINDOW_HEIGHT) // 2, 0)
        self.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}+{x}+{y}")

    def translate(self, key: str, **values: Any) -> str:
        """Return the text for ``key`` in the selected language."""
        return TRANSLATIONS[self.language][key].format(**values)

    def show_frame(self, name: str) -> None:
        frame = self.frames[name]
        frame.tkraise()
        frame.update_texts()

    def on_close(self) -> None:
        """Ask before closing while the bot is running, then clean up the browser."""
        if self.is_running and not messagebox.askyesno(
            self.translate("confirm_title"), self.translate("confirm_quit")
        ):
            return
        self.stop_event.set()
        if self.driver is not None:
            try:
                self.driver.quit()
            except Exception:  # noqa: BLE001 - the browser may already be closed
                logger.debug("Could not quit the browser cleanly", exc_info=True)
        self.destroy()


class WizardFrame(ttk.Frame):
    """Base class of the wizard steps.

    Widgets go into ``self.content``, a frame that is centred in the window both
    horizontally and vertically.
    """

    def __init__(self, parent: Any, controller: UnlikeWizard) -> None:
        super().__init__(parent)
        self.controller = controller
        self.content = ttk.Frame(self)
        self.content.place(relx=0.5, rely=0.5, anchor="center")

    def add_navigation(
        self,
        on_back: Callable[[], None],
        on_next: Callable[[], None] | None = None,
        next_state: str = "normal",
    ) -> tuple[ttk.Button, ttk.Button | None]:
        """Add a centred row with a Back button and, optionally, a Next button."""
        row = ttk.Frame(self.content)
        row.pack(pady=(25, 0))
        back_button = ttk.Button(row, command=on_back)
        back_button.pack(side="left", padx=8)
        next_button = None
        if on_next is not None:
            next_button = ttk.Button(row, command=on_next, state=next_state)
            next_button.pack(side="left", padx=8)
        return back_button, next_button

    def translate(self, key: str, **values: Any) -> str:
        return self.controller.translate(key, **values)

    def update_texts(self) -> None:
        """Refresh the texts. Called every time this step is shown."""


class FileBrowseRow(ttk.Frame):
    """A read-only path box with a Browse button that picks a JSON file."""

    def __init__(self, parent: Any, on_selected: Callable[[str], None]) -> None:
        super().__init__(parent)
        self.on_selected = on_selected
        self.entry = ttk.Entry(self, width=40, state="readonly")
        self.entry.pack(side="left", padx=5)
        self.button = ttk.Button(self, command=self._browse)
        self.button.pack(side="left")

    def _browse(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("JSON Files", "*.json")])
        if path:
            self.set_path(path)
            self.on_selected(path)

    def set_path(self, path: str) -> None:
        self.entry.config(state="normal")
        self.entry.delete(0, tk.END)
        self.entry.insert(0, path)
        self.entry.config(state="readonly")


class LanguageFrame(WizardFrame):
    """Step 1: choose the interface language."""

    def __init__(self, parent: Any, controller: UnlikeWizard) -> None:
        super().__init__(parent, controller)
        ttk.Label(
            self.content, text="1. Dil Seçimi / Language", font=("Helvetica", 16, "bold")
        ).pack(pady=(0, 30))
        ttk.Button(self.content, text="Türkçe", command=lambda: self.select_language("tr")).pack(
            pady=10, ipadx=20, ipady=10
        )
        ttk.Button(self.content, text="English", command=lambda: self.select_language("en")).pack(
            pady=10, ipadx=20, ipady=10
        )

    def select_language(self, language: str) -> None:
        self.controller.language = language
        self.controller.title(self.translate("title"))
        self.controller.show_frame("WhitelistFrame")


class WhitelistFrame(WizardFrame):
    """Step 2: optionally choose one or more followers/following files to protect."""

    def __init__(self, parent: Any, controller: UnlikeWizard) -> None:
        super().__init__(parent, controller)
        self.title_label = ttk.Label(self.content, font=("Helvetica", 14, "bold"))
        self.title_label.pack(pady=(0, 15))

        self.question_label = ttk.Label(self.content, justify="center", wraplength=WRAP_LENGTH)
        self.question_label.pack(pady=10)

        self.yes_radio = ttk.Radiobutton(
            self.content, variable=controller.use_whitelist, value=True, command=self.toggle_browse
        )
        self.yes_radio.pack(pady=5)
        self.no_radio = ttk.Radiobutton(
            self.content, variable=controller.use_whitelist, value=False, command=self.toggle_browse
        )
        self.no_radio.pack(pady=5)

        # Shown only when "use whitelist" is selected
        self.browse_area = ttk.Frame(self.content)
        self.select_label = ttk.Label(self.browse_area, justify="center", wraplength=WRAP_LENGTH)
        self.select_label.pack()
        self.file_list = tk.Listbox(
            self.browse_area, width=52, height=4, selectmode="extended", activestyle="none"
        )
        self.file_list.pack(pady=6)
        button_row = ttk.Frame(self.browse_area)
        button_row.pack()
        self.add_button = ttk.Button(button_row, command=self.browse_files)
        self.add_button.pack(side="left", padx=5)
        self.remove_button = ttk.Button(button_row, command=self.remove_selected)
        self.remove_button.pack(side="left", padx=5)
        self.total_label = ttk.Label(self.browse_area, foreground="blue")
        self.total_label.pack(pady=(8, 0))

        self.back_button, self.next_button = self.add_navigation(
            on_back=lambda: controller.show_frame("LanguageFrame"),
            on_next=self.validate_and_next,
        )

    def browse_files(self) -> None:
        """Let the user pick one or several JSON files at once."""
        paths = filedialog.askopenfilenames(filetypes=[("JSON Files", "*.json")])
        self.add_files(list(paths))

    def add_files(self, paths: Iterable[str]) -> None:
        """Read each file right away, so a bad file is reported while the user is looking."""
        sources = self.controller.whitelist_sources
        for path in paths:
            if path in sources:
                continue
            name = Path(path).name
            try:
                usernames = read_whitelist_usernames(path)
            except (OSError, ValueError):  # unreadable file, bad JSON or bad encoding
                logger.warning("Could not read whitelist file %s", path, exc_info=True)
                messagebox.showerror(
                    self.translate("error_title"),
                    self.translate("whitelist_file_invalid", name=name),
                )
                continue
            if not usernames:
                messagebox.showerror(
                    self.translate("error_title"),
                    self.translate("whitelist_file_empty", name=name),
                )
                continue
            sources[path] = usernames
        self.refresh_file_list()

    def remove_selected(self) -> None:
        sources = self.controller.whitelist_sources
        paths = list(sources)
        for index in self.file_list.curselection():
            sources.pop(paths[index], None)
        self.refresh_file_list()

    def refresh_file_list(self) -> None:
        """Show the chosen files with their username counts, and the combined total."""
        sources = self.controller.whitelist_sources
        self.file_list.delete(0, tk.END)
        for path, usernames in sources.items():
            self.file_list.insert(
                tk.END,
                self.translate("whitelist_item", name=Path(path).name, count=len(usernames)),
            )
        total = len(merge_usernames(sources.values()))
        self.total_label.config(text=self.translate("whitelist_total", count=total))

    def toggle_browse(self) -> None:
        if self.controller.use_whitelist.get():
            self.browse_area.pack(after=self.no_radio, pady=15)
        else:
            self.browse_area.pack_forget()

    def validate_and_next(self) -> None:
        controller = self.controller
        if controller.use_whitelist.get():
            if not controller.whitelist_sources:
                messagebox.showerror(self.translate("error_title"), self.translate("err_nofile"))
                return
            controller.whitelist_usernames = merge_usernames(controller.whitelist_sources.values())
        else:
            controller.whitelist_usernames = set()
        controller.show_frame("LikesFrame")

    def update_texts(self) -> None:
        self.title_label.config(text=self.translate("step2_title"))
        self.question_label.config(text=self.translate("whitelist_question"))
        self.yes_radio.config(text=self.translate("yes"))
        self.no_radio.config(text=self.translate("no"))
        self.select_label.config(text=self.translate("whitelist_select"))
        self.add_button.config(text=self.translate("add_files"))
        self.remove_button.config(text=self.translate("remove_selected"))
        self.next_button.config(text=self.translate("next"))
        self.back_button.config(text=self.translate("back"))
        self.refresh_file_list()
        self.toggle_browse()


class LikesFrame(WizardFrame):
    """Step 3: choose liked_posts.json and see how many posts will be unliked."""

    def __init__(self, parent: Any, controller: UnlikeWizard) -> None:
        super().__init__(parent, controller)
        self.title_label = ttk.Label(self.content, font=("Helvetica", 14, "bold"))
        self.title_label.pack(pady=20)

        self.select_label = ttk.Label(self.content)
        self.select_label.pack(pady=5)

        self.browse_row = FileBrowseRow(self.content, on_selected=self.process_likes_file)
        self.browse_row.pack(pady=5)

        self.stats_label = ttk.Label(
            self.content,
            justify="center",
            font=("Helvetica", 10, "bold"),
            foreground="blue",
            wraplength=WRAP_LENGTH,
        )
        self.stats_label.pack(pady=20)

        self.back_button, self.next_button = self.add_navigation(
            on_back=lambda: controller.show_frame("WhitelistFrame"),
            on_next=lambda: controller.show_frame("LoginFrame"),
            next_state="disabled",
        )

    def process_likes_file(self, path: str) -> None:
        """Read the chosen file, apply the whitelist and skip posts finished earlier."""
        controller = self.controller
        controller.likes_path = path
        self.next_button.config(state="disabled")
        try:
            posts, unreadable = parse_liked_posts(load_json_file(path))
        except InvalidExportError:
            logger.warning("Unexpected structure in %s", path)
            messagebox.showerror(self.translate("error_title"), self.translate("invalid_structure"))
            return
        except (OSError, ValueError):  # unreadable file, bad JSON or bad encoding
            logger.warning("Could not read likes file", exc_info=True)
            messagebox.showerror(self.translate("error_title"), self.translate("invalid_json"))
            return

        whitelist = controller.whitelist_usernames if controller.use_whitelist.get() else None
        targets, protected, unknown_owner = select_targets(posts, whitelist)

        store = ProgressStore(path)
        done_urls = store.load_done_urls()
        remaining = [post for post in targets if post.url not in done_urls]

        controller.targets = remaining
        controller.progress_store = store
        self.stats_label.config(
            text=self.translate(
                "stats",
                total=len(posts) + unreadable,
                protected=protected,
                skipped=unreadable + unknown_owner,
                done=len(targets) - len(remaining),
                targets=len(remaining),
            )
        )

        if remaining:
            self.next_button.config(state="normal")
        elif targets:
            messagebox.showinfo(self.translate("info_title"), self.translate("nothing_left"))
        else:
            messagebox.showinfo(self.translate("info_title"), self.translate("err_notarget"))

    def update_texts(self) -> None:
        self.title_label.config(text=self.translate("step3_title"))
        self.select_label.config(text=self.translate("likes_select"))
        self.browse_row.button.config(text=self.translate("browse"))
        self.next_button.config(text=self.translate("next"), state="disabled")
        self.back_button.config(text=self.translate("back"))
        self.stats_label.config(text="")
        self.browse_row.set_path("")


class LoginFrame(WizardFrame):
    """Step 4: open Chrome, let the user log in, then start."""

    def __init__(self, parent: Any, controller: UnlikeWizard) -> None:
        super().__init__(parent, controller)
        self.title_label = ttk.Label(self.content, font=("Helvetica", 14, "bold"))
        self.title_label.pack(pady=20)

        self.warning_label = ttk.Label(
            self.content, justify="center", foreground="red", wraplength=WRAP_LENGTH
        )
        self.warning_label.pack(pady=10)

        self.chrome_button = ttk.Button(self.content, command=self.open_chrome)
        self.chrome_button.pack(pady=15, ipadx=10, ipady=10)

        self.ready_button = ttk.Button(self.content, command=self.start_process, state="disabled")
        self.ready_button.pack(pady=15, ipadx=10, ipady=10)

        self.status_label = ttk.Label(self.content)
        self.status_label.pack(pady=5)

        self.back_button, _ = self.add_navigation(
            on_back=lambda: controller.show_frame("LikesFrame")
        )

    def open_chrome(self) -> None:
        """Start Chrome in a background thread so the window does not freeze."""
        self.chrome_button.config(state="disabled")
        self.back_button.config(state="disabled")
        self.status_label.config(text=self.translate("opening_chrome"))
        threading.Thread(target=self._launch_browser, daemon=True).start()

    def _launch_browser(self) -> None:
        try:
            driver = start_chrome()
            driver.get(INSTAGRAM_URL)
        except Exception as error:  # noqa: BLE001 - show whatever went wrong to the user
            logger.exception("Could not start Chrome")
            self.after(0, self._on_browser_failed, short_error_message(error))
        else:
            self.after(0, self._on_browser_ready, driver)

    def _on_browser_ready(self, driver: Any) -> None:
        self.controller.driver = driver
        self.status_label.config(text="")
        self.ready_button.config(state="normal")

    def _on_browser_failed(self, error: str) -> None:
        messagebox.showerror(
            self.translate("chrome_error_title"), self.translate("chrome_error", error=error)
        )
        self.status_label.config(text="")
        self.chrome_button.config(state="normal")
        self.back_button.config(state="normal")

    def start_process(self) -> None:
        if not self._looks_logged_in() and not messagebox.askyesno(
            self.translate("confirm_title"), self.translate("not_logged_in")
        ):
            return
        self.controller.show_frame("ProgressFrame")
        progress_frame = self.controller.frames["ProgressFrame"]
        progress_frame.start_session()

    def _looks_logged_in(self) -> bool:
        """Best-effort check: a logged-in browser has an Instagram "sessionid" cookie."""
        try:
            return self.controller.driver.get_cookie("sessionid") is not None
        except Exception:  # noqa: BLE001 - e.g. the browser window was closed
            return False

    def update_texts(self) -> None:
        self.title_label.config(text=self.translate("step4_title"))
        self.warning_label.config(text=self.translate("login_warn"))
        self.chrome_button.config(text=self.translate("open_chrome"), state="normal")
        self.ready_button.config(text=self.translate("ready_btn"), state="disabled")
        self.back_button.config(text=self.translate("back"), state="normal")
        self.status_label.config(text="")


class ProgressFrame(WizardFrame):
    """Step 5: run the session on a worker thread and show its progress."""

    def __init__(self, parent: Any, controller: UnlikeWizard) -> None:
        super().__init__(parent, controller)
        self.title_label = ttk.Label(self.content, font=("Helvetica", 14, "bold"))
        self.title_label.pack(pady=20)

        self.progress_bar = ttk.Progressbar(
            self.content, orient="horizontal", length=400, mode="determinate"
        )
        self.progress_bar.pack(pady=15)

        self.count_label = ttk.Label(self.content, font=("Helvetica", 12))
        self.count_label.pack(pady=5)

        self.counters_label = ttk.Label(self.content)
        self.counters_label.pack(pady=5)

        self.status_label = ttk.Label(self.content, foreground="green")
        self.status_label.pack(pady=10)

        self.stop_button = ttk.Button(self.content, command=self.request_stop)
        self.stop_button.pack(pady=15)

    def update_texts(self) -> None:
        self.title_label.config(text=self.translate("step5_title"))
        self.stop_button.config(text=self.translate("stop"))
        if not self.controller.is_running:
            self.count_label.config(text=self.translate("status_init"))
            self.counters_label.config(text="")
            self.status_label.config(text="")

    def start_session(self) -> None:
        """Start unliking on a background thread."""
        controller = self.controller
        if controller.is_running:
            return
        controller.is_running = True
        controller.stop_event.clear()
        self.progress_bar["value"] = 0
        self.progress_bar["maximum"] = max(len(controller.targets), 1)
        self.stop_button.config(state="normal")
        threading.Thread(target=self._run_worker, daemon=True).start()

    def request_stop(self) -> None:
        self.controller.stop_event.set()
        self.stop_button.config(state="disabled")
        self.status_label.config(text=self.translate("stopping"))

    # -- worker thread -------------------------------------------------------

    def _run_worker(self) -> None:
        controller = self.controller
        log_handler = self._attach_log_file()
        summary: SessionSummary | None = None
        try:
            session = UnlikeSession(
                controller.driver,
                controller.targets,
                controller.progress_store,
                controller.stop_event,
                self._on_progress,
            )
            summary = session.run()
        except Exception:  # noqa: BLE001 - report instead of dying silently in a thread
            logger.exception("Unexpected error during the unlike session")
        finally:
            if log_handler is not None:
                logger.removeHandler(log_handler)
                log_handler.close()
            try:
                controller.driver.quit()
            except Exception:  # noqa: BLE001 - the browser may already be closed
                logger.debug("Could not quit the browser cleanly", exc_info=True)
        self._call_in_ui_thread(self._finish, summary)

    def _attach_log_file(self) -> logging.Handler | None:
        """Log to a file next to the likes file (it contains post URLs from your export)."""
        likes_path = Path(self.controller.likes_path)
        try:
            log_path = likes_path.with_name(likes_path.stem + ".log")
            handler = logging.FileHandler(log_path, "a", "utf-8")
        except OSError:
            return None
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        return handler

    def _on_progress(self, update: ProgressUpdate) -> None:
        self._call_in_ui_thread(self._apply_progress, update)

    def _call_in_ui_thread(self, function: Callable[..., None], *args: Any) -> None:
        try:
            self.after(0, function, *args)
        except (tk.TclError, RuntimeError):
            pass  # the window was closed while the worker was still running

    # -- UI thread -----------------------------------------------------------

    def _apply_progress(self, update: ProgressUpdate) -> None:
        self.progress_bar["maximum"] = max(update.total, 1)
        self.progress_bar["value"] = update.current
        self.count_label.config(
            text=self.translate(
                "status_working",
                current=update.current,
                total=update.total,
                post=update.post.short_id,
            )
        )
        self.counters_label.config(
            text=self.translate(
                "counters",
                unliked=update.unliked,
                already=update.already_unliked,
                unverified=update.unverified,
            )
        )
        self.status_label.config(
            text=self.translate(update.status, seconds=round(update.seconds, 1))
        )

    def _finish(self, summary: SessionSummary | None) -> None:
        self.controller.is_running = False
        self.stop_button.config(state="disabled")
        self.status_label.config(text="")
        if summary is None:
            messagebox.showerror(self.translate("error_title"), self.translate("unexpected_error"))
            return
        if summary.reason is StopReason.FINISHED:
            self.progress_bar["value"] = self.progress_bar["maximum"]
        parts = [
            self.translate(
                f"summary_{summary.reason.value}", limit=MAX_CONSECUTIVE_FAILURES
            ),
            self.translate(
                "summary_counts",
                unliked=summary.unliked,
                already=summary.already_unliked,
                unverified=summary.unverified,
            ),
        ]
        if summary.unverified:
            parts.append(self.translate("summary_hint"))
        messagebox.showinfo(self.translate("done_title"), "\n\n".join(parts))


def main() -> None:
    """Start the application."""
    if sys.stderr is not None:  # a windowed executable has no console
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    UnlikeWizard().mainloop()


if __name__ == "__main__":
    main()
