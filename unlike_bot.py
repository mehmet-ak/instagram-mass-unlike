import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import json
import time
import random
import sys
import os
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.action_chains import ActionChains

UI = {
    "tr": {
        "title": "Instagram Toplu Beğeni Silici",
        "next": "İleri >",
        "back": "< Geri",
        "browse": "Gözat...",
        "step1_title": "1. Dil Seçimi / Language",
        "step2_title": "2. İstisna (Whitelist) Ayarı",
        "wl_q": "İstisna (Whitelist) kullanmak istiyor musunuz?\n(Takip ettiklerinizin beğenileri silinmez)",
        "yes": "Evet, kullan",
        "no": "Hayır, herkesi sil",
        "wl_sel": "Lütfen takipçi (following/followers) JSON dosyasını seçin:",
        "step3_title": "3. Beğeni Dosyası Seçimi",
        "likes_sel": "Lütfen beğenilerin (liked_posts.json) dosyasını seçin:",
        "invalid_json": "Seçilen dosya geçerli bir JSON değil veya bozuk!",
        "no_data": "Dosyada uygun veri bulunamadı.",
        "stats": "Toplam Beğeni: {0}\nKorumaya Alınan: {1}\nSilinecek Hedef: {2}",
        "step4_title": "4. Giriş ve Onay",
        "open_chrome": "1. Chrome'u Aç ve Giriş Yap",
        "ready_btn": "2. Hazırız! İşlemi Başlat",
        "login_warn": "Tarayıcı açıldığında Instagram'a giriş yapın.\nGirişiniz tamamen bittikten sonra 2. butona tıklayın.",
        "step5_title": "5. İşlem Durumu",
        "status_init": "Başlatılıyor...",
        "status_working": "[{0}/{1}] İşleniyor: {2}",
        "status_wait": "Bot Koruması: {0} saniye bekleniyor...",
        "status_long_wait": "UZUN MOLA: Spam koruması için 5 dk bekleniyor...",
        "status_done": "Tüm işlemler başarıyla tamamlandı!",
        "err_nofile": "Lütfen önce bir dosya seçin!",
        "err_notarget": "Silinecek hiçbir URL bulunamadı!"
    },
    "en": {
        "title": "Instagram Mass Unlike Bot",
        "next": "Next >",
        "back": "< Back",
        "browse": "Browse...",
        "step1_title": "1. Language Selection",
        "step2_title": "2. Whitelist Settings",
        "wl_q": "Do you want to use a Whitelist?\n(Keep likes of people you follow)",
        "yes": "Yes, use whitelist",
        "no": "No, target everyone",
        "wl_sel": "Please select your followers/following JSON file:",
        "step3_title": "3. Select Likes File",
        "likes_sel": "Please select your likes (liked_posts.json) file:",
        "invalid_json": "Selected file is not a valid JSON or corrupted!",
        "no_data": "No suitable data found in the file.",
        "stats": "Total Likes: {0}\nProtected: {1}\nTargets to Unlike: {2}",
        "step4_title": "4. Login & Confirm",
        "open_chrome": "1. Open Chrome & Login",
        "ready_btn": "2. Ready! Start Process",
        "login_warn": "When the browser opens, log in to Instagram.\nClick the 2nd button ONLY after you are fully logged in.",
        "step5_title": "5. Progress Status",
        "status_init": "Starting...",
        "status_working": "[{0}/{1}] Processing: {2}",
        "status_wait": "Bot Protection: Waiting {0} seconds...",
        "status_long_wait": "LONG BREAK: Waiting 5 mins to avoid spam filter...",
        "status_done": "All tasks completed successfully!",
        "err_nofile": "Please select a file first!",
        "err_notarget": "No URLs found to unlike!"
    }
}

class UnlikeWizard(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Instagram Mass Unlike Bot")
        self.geometry("550x400")
        self.resizable(False, False)
        
        # State Variables
        self.lang = "tr"
        self.use_whitelist = tk.BooleanVar(value=False)
        self.wl_file_path = ""
        self.likes_file_path = ""
        self.whitelist_users = []
        self.target_urls = []
        self.all_likes_data = []
        self.driver = None
        self.is_running = False

        # Container for frames
        self.container = ttk.Frame(self)
        self.container.pack(fill="both", expand=True)

        self.frames = {}
        for F in (LangFrame, WhitelistFrame, LikesFrame, LoginFrame, ProgressFrame):
            page_name = F.__name__
            frame = F(parent=self.container, controller=self)
            self.frames[page_name] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        self.show_frame("LangFrame")

    def get_text(self, key, *args):
        text = UI[self.lang][key]
        if args:
            return text.format(*args)
        return text

    def show_frame(self, page_name):
        frame = self.frames[page_name]
        frame.tkraise()
        frame.update_texts()


class LangFrame(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        
        ttk.Label(self, text="1. Dil Seçimi / Language", font=("Helvetica", 16, "bold")).pack(pady=40)
        
        btn_tr = ttk.Button(self, text="Türkçe", command=lambda: self.set_lang("tr"))
        btn_tr.pack(pady=10, ipadx=20, ipady=10)
        
        btn_en = ttk.Button(self, text="English", command=lambda: self.set_lang("en"))
        btn_en.pack(pady=10, ipadx=20, ipady=10)

    def set_lang(self, lang):
        self.controller.lang = lang
        self.controller.title(self.controller.get_text("title"))
        self.controller.show_frame("WhitelistFrame")
        
    def update_texts(self):
        pass


class WhitelistFrame(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        
        self.lbl_title = ttk.Label(self, font=("Helvetica", 14, "bold"))
        self.lbl_title.pack(pady=20)

        self.lbl_q = ttk.Label(self, justify="center")
        self.lbl_q.pack(pady=10)

        self.radio_yes = ttk.Radiobutton(self, variable=self.controller.use_whitelist, value=True, command=self.toggle_browse)
        self.radio_yes.pack(pady=5)
        self.radio_no = ttk.Radiobutton(self, variable=self.controller.use_whitelist, value=False, command=self.toggle_browse)
        self.radio_no.pack(pady=5)

        self.frame_browse = ttk.Frame(self)
        self.lbl_wl_sel = ttk.Label(self.frame_browse)
        self.lbl_wl_sel.pack()
        
        browse_row = ttk.Frame(self.frame_browse)
        browse_row.pack(pady=5)
        self.entry_path = ttk.Entry(browse_row, width=40, state="readonly")
        self.entry_path.pack(side="left", padx=5)
        self.btn_browse = ttk.Button(browse_row, command=self.browse_file)
        self.btn_browse.pack(side="left")

        self.btn_next = ttk.Button(self, command=self.validate_and_next)
        self.btn_next.pack(side="bottom", pady=20)
        self.btn_back = ttk.Button(self, command=lambda: self.controller.show_frame("LangFrame"))
        self.btn_back.pack(side="bottom")

    def toggle_browse(self):
        if self.controller.use_whitelist.get():
            self.frame_browse.pack(pady=15)
        else:
            self.frame_browse.pack_forget()

    def browse_file(self):
        path = filedialog.askopenfilename(filetypes=[("JSON Files", "*.json")])
        if path:
            self.entry_path.config(state="normal")
            self.entry_path.delete(0, tk.END)
            self.entry_path.insert(0, path)
            self.entry_path.config(state="readonly")
            self.controller.wl_file_path = path

    def validate_and_next(self):
        if self.controller.use_whitelist.get():
            if not self.controller.wl_file_path:
                messagebox.showerror("Hata / Error", self.controller.get_text("err_nofile"))
                return
            
            # JSON Doğrulama
            kullanicilar = set()
            try:
                with open(self.controller.wl_file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                def tarayici(obj):
                    if isinstance(obj, dict):
                        if "string_list_data" in obj:
                            for s_item in obj["string_list_data"]:
                                val = s_item.get("value")
                                if val:
                                    kullanicilar.add(val.lower())
                        for v in obj.values():
                            tarayici(v)
                    elif isinstance(obj, list):
                        for item in obj:
                            tarayici(item)
                
                tarayici(data)
                self.controller.whitelist_users = list(kullanicilar)
                
            except Exception:
                messagebox.showerror("Hata / Error", self.controller.get_text("invalid_json"))
                return

        self.controller.show_frame("LikesFrame")

    def update_texts(self):
        c = self.controller
        self.lbl_title.config(text=c.get_text("step2_title"))
        self.lbl_q.config(text=c.get_text("wl_q"))
        self.radio_yes.config(text=c.get_text("yes"))
        self.radio_no.config(text=c.get_text("no"))
        self.lbl_wl_sel.config(text=c.get_text("wl_sel"))
        self.btn_browse.config(text=c.get_text("browse"))
        self.btn_next.config(text=c.get_text("next"))
        self.btn_back.config(text=c.get_text("back"))
        self.toggle_browse()


class LikesFrame(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        
        self.lbl_title = ttk.Label(self, font=("Helvetica", 14, "bold"))
        self.lbl_title.pack(pady=20)

        self.lbl_likes_sel = ttk.Label(self)
        self.lbl_likes_sel.pack(pady=5)

        browse_row = ttk.Frame(self)
        browse_row.pack(pady=5)
        self.entry_path = ttk.Entry(browse_row, width=40, state="readonly")
        self.entry_path.pack(side="left", padx=5)
        self.btn_browse = ttk.Button(browse_row, command=self.browse_file)
        self.btn_browse.pack(side="left")

        self.lbl_stats = ttk.Label(self, justify="center", font=("Helvetica", 10, "bold"), foreground="blue")
        self.lbl_stats.pack(pady=20)

        self.btn_next = ttk.Button(self, command=self.go_next, state="disabled")
        self.btn_next.pack(side="bottom", pady=20)
        self.btn_back = ttk.Button(self, command=lambda: self.controller.show_frame("WhitelistFrame"))
        self.btn_back.pack(side="bottom")

    def browse_file(self):
        path = filedialog.askopenfilename(filetypes=[("JSON Files", "*.json")])
        if path:
            self.entry_path.config(state="normal")
            self.entry_path.delete(0, tk.END)
            self.entry_path.insert(0, path)
            self.entry_path.config(state="readonly")
            self.controller.likes_file_path = path
            self.process_likes_file()

    def process_likes_file(self):
        try:
            with open(self.controller.likes_file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            messagebox.showerror("Hata / Error", self.controller.get_text("invalid_json"))
            self.btn_next.config(state="disabled")
            return

        silinecekler = []
        istisnalar = self.controller.whitelist_users if self.controller.use_whitelist.get() else []

        for item in data:
            url, username = "", ""
            for label_obj in item.get("label_values", []):
                if "href" in label_obj:
                    url = label_obj.get("href")
                    
                title = str(label_obj.get("title", ""))
                if "Owner" in title or "Sahibi" in title:
                    for owner_item in label_obj.get("dict", []):
                        for prop in owner_item.get("dict", []):
                            p_lbl = str(prop.get("label", ""))
                            if "Username" in p_lbl or "Kullan" in p_lbl:
                                username = prop.get("value")
            
            if url and username:
                if not istisnalar or username.lower() not in istisnalar:
                    silinecekler.append({"url": url, "raw_data": item})

        self.controller.all_likes_data = data
        self.controller.target_urls = silinecekler
        
        total = len(data)
        targets = len(silinecekler)
        protected = total - targets
        
        self.lbl_stats.config(text=self.controller.get_text("stats", total, protected, targets))
        
        if targets > 0:
            self.btn_next.config(state="normal")
        else:
            self.btn_next.config(state="disabled")
            messagebox.showinfo("Bilgi / Info", self.controller.get_text("err_notarget"))

    def go_next(self):
        self.controller.show_frame("LoginFrame")

    def update_texts(self):
        c = self.controller
        self.lbl_title.config(text=c.get_text("step3_title"))
        self.lbl_likes_sel.config(text=c.get_text("likes_sel"))
        self.btn_browse.config(text=c.get_text("browse"))
        self.btn_next.config(text=c.get_text("next"))
        self.btn_back.config(text=c.get_text("back"))
        self.lbl_stats.config(text="")
        self.btn_next.config(state="disabled")
        self.entry_path.config(state="normal")
        self.entry_path.delete(0, tk.END)
        self.entry_path.config(state="readonly")


class LoginFrame(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        
        self.lbl_title = ttk.Label(self, font=("Helvetica", 14, "bold"))
        self.lbl_title.pack(pady=20)

        self.lbl_warn = ttk.Label(self, justify="center", foreground="red")
        self.lbl_warn.pack(pady=10)

        self.btn_chrome = ttk.Button(self, command=self.open_chrome)
        self.btn_chrome.pack(pady=15, ipadx=10, ipady=10)

        self.btn_ready = ttk.Button(self, command=self.start_process, state="disabled")
        self.btn_ready.pack(pady=15, ipadx=10, ipady=10)

        self.btn_back = ttk.Button(self, command=lambda: self.controller.show_frame("LikesFrame"))
        self.btn_back.pack(side="bottom", pady=20)

    def open_chrome(self):
        self.btn_chrome.config(state="disabled")
        self.btn_back.config(state="disabled")
        
        try:
            options = uc.ChromeOptions()
            self.controller.driver = uc.Chrome(options=options)
            self.controller.driver.get("https://www.instagram.com/")
            self.btn_ready.config(state="normal")
        except Exception as e:
            messagebox.showerror("Chrome Hatası", str(e))
            self.btn_chrome.config(state="normal")
            self.btn_back.config(state="normal")

    def start_process(self):
        self.controller.show_frame("ProgressFrame")

    def update_texts(self):
        c = self.controller
        self.lbl_title.config(text=c.get_text("step4_title"))
        self.lbl_warn.config(text=c.get_text("login_warn"))
        self.btn_chrome.config(text=c.get_text("open_chrome"), state="normal")
        self.btn_ready.config(text=c.get_text("ready_btn"), state="disabled")
        self.btn_back.config(text=c.get_text("back"), state="normal")


class ProgressFrame(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        
        self.lbl_title = ttk.Label(self, font=("Helvetica", 14, "bold"))
        self.lbl_title.pack(pady=20)

        self.progress = ttk.Progressbar(self, orient="horizontal", length=400, mode="determinate")
        self.progress.pack(pady=20)

        self.lbl_count = ttk.Label(self, font=("Helvetica", 12))
        self.lbl_count.pack(pady=5)
        
        self.lbl_status = ttk.Label(self, foreground="green")
        self.lbl_status.pack(pady=10)

    def update_texts(self):
        c = self.controller
        self.lbl_title.config(text=c.get_text("step5_title"))
        self.lbl_count.config(text=c.get_text("status_init"))
        self.lbl_status.config(text="")
        
        if not c.is_running:
            c.is_running = True
            threading.Thread(target=self.run_unlike_process, daemon=True).start()

    def update_ui(self, count, total, url, status_msg):
        self.progress["value"] = count
        self.progress["maximum"] = total
        self.lbl_count.config(text=self.controller.get_text("status_working", count, total, url.split("/")[-2] if "/" in url else url))
        self.lbl_status.config(text=status_msg)

    def run_unlike_process(self):
        c = self.controller
        driver = c.driver
        hedef_liste = c.target_urls
        tum_data = c.all_likes_data
        likes_file = c.likes_file_path
        
        basarili = 0
        total = len(hedef_liste)

        for index, hedef in enumerate(hedef_liste):
            url = hedef["url"]
            islem_tamam = False
            
            try:
                self.controller.after(0, self.update_ui, index, total, url, "Yükleniyor / Loading...")
                driver.get(url)
                time.sleep(random.uniform(4, 7))
                
                unlike_xpath = "//*[local-name()='svg' and (@aria-label='Unlike' or @aria-label='Beğenmekten Vazgeç')]/ancestor::div[@role='button']"
                
                try:
                    unlike_button = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.XPATH, unlike_xpath))
                    )
                    time.sleep(random.uniform(1.0, 2.5))
                    try:
                        ActionChains(driver).move_to_element(unlike_button).pause(random.uniform(0.3, 0.9)).click().perform()
                    except:
                        driver.execute_script("arguments[0].click();", unlike_button)
                        
                    basarili += 1
                    islem_tamam = True
                    msg = "Başarılı / Success"
                    
                except TimeoutException:
                    islem_tamam = True
                    msg = "Zaten silinmiş / Already unliked"
                    
            except Exception as e:
                msg = f"Hata / Error"

            if islem_tamam:
                try:
                    tum_data.remove(hedef["raw_data"])
                    with open(likes_file, "w", encoding="utf-8") as f:
                        json.dump(tum_data, f, ensure_ascii=False, indent=2)
                except ValueError:
                    pass

            if index < total - 1:
                bekleme = random.uniform(15, 25)
                self.controller.after(0, self.update_ui, index + 1, total, url, c.get_text("status_wait", round(bekleme, 1)))
                time.sleep(bekleme)
                
                if basarili > 0 and basarili % 35 == 0:
                    self.controller.after(0, self.update_ui, index + 1, total, url, c.get_text("status_long_wait"))
                    time.sleep(300)

        self.controller.after(0, self.finish_process)

    def finish_process(self):
        self.lbl_count.config(text=self.controller.get_text("status_done"))
        self.lbl_status.config(text="")
        self.progress["value"] = self.progress["maximum"]
        messagebox.showinfo("Bitti / Done", self.controller.get_text("status_done"))
        try:
            self.controller.driver.quit()
        except:
            pass


if __name__ == "__main__":
    app = UnlikeWizard()
    app.mainloop()