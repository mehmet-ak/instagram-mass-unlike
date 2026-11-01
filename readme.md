# Instagram Mass Unlike Bot

> **⚠️ IMPORTANT DISCLAIMER**
> 
> **1. AI Usage:** I used AI a lot. By a lot, I mean A LOT. So, if you are uncomfortable with using a tool made mostly by AI, you can skip this.
> 
> **2. Rate Limit & Safety:** Due to Instagram's API restrictions, performing more than 100-150 actions per day may result in a temporary "Action Block". The script is intentionally designed with random wait times (15-25s) and 5-minute long breaks every 35 actions. Please do not decrease these timers to keep your account safe. However, this tool still can cause problems. This means, SAFETY IS NOT GUARANTEED! Therefore, use this at your own risk. By installing and using this tool, you accept doing this at your own risk.
> 
> **3. Privacy & Security:** Absolutely no risk of giving your files to a 3rd party. I used completely open-sourced software and even this project is open-sourced. Feel free to use this tool without any risks of getting hacked.


## INFO
This tool automatically removes your likes from thousands of Instagram posts while allowing you to protect (whitelist) specific users, such as people you follow. It features a full Graphical User Interface for ease of use.

Standalone executables for both Windows (`.exe`) and Linux are provided. No Python installation is required for end-users.

## Features
- **User-Friendly GUI:** A complete, interactive wizard interface built with Tkinter. No more command-line interactions.
- **Smart Whitelist:** Easily browse and select your `following.json` (or any follower list) to automatically skip unliking posts from your protected users.
- **Auto-Save / Crash Recovery:** Every time a like is successfully removed (or if the post is already deleted), it is permanently removed from your `liked_posts.json` file. If your internet disconnects or you hit a rate limit, simply run the bot again; it will resume exactly where it left off.
- **Undetected Chromedriver:** Bypasses Instagram's automated bot detection systems (WebDriver flags). ***Again, NOT GUARANTEED!***
- **Human-like Interaction:** Uses a hybrid clicking method (ActionChains + JS) to solve the scroll-snapping issue on Reels without scrolling physically.
- **Multi-Language Support:** The setup wizard natively supports both English and Turkish.

## How to Get Your Data (All Users)
1. On Instagram (app or web), navigate to `Settings > Accounts Center > Your information and permissions > Download your information`.
2. Download only the **Likes** and **Followers and Following** categories in **JSON** format.
3. Extract the downloaded archive. You will need the `liked_posts.json` file and your whitelist file (e.g., `following.json` or `followers_1.json`).

## Usage for Windows Users
If you don't want to deal with Python, use the compiled executable:
1. Download the `Windows-Release.zip` from the **[Releases]** tab and extract it.
2. Double-click the `.exe` file to run the program. 
3. Follow the on-screen wizard: Select your language, choose if you want a whitelist, and browse to select your JSON files.
4. When prompted in Step 4, click the button to open Chrome and log in to your Instagram account.
5. After you are fully logged in, return to the application window and click the second button to start the process. The progress bar will show real-time updates.

## Usage for Linux Users
1. Download the `Linux-Release.zip` from the **[Releases]** tab and extract it.
2. Open your terminal and grant execution permission to the file:
   ```bash
   chmod +x InstagramMassUnlike-LinuxGUI
   ```
3. Run the executable:
    ```bash
    ./InstagramMassUnlike-LinuxGUI
    ```
4. Follow the on-screen GUI wizard just like the Windows version.

## For Developers
If you want to run the project from the source code:
1. Clone and setup environment
    ```bash
    python3 -m venv bot_env
    ```

    On Linux:
    ```bash
    source bot_env/bin/activate
    ```

    On Windows:
    ```bash
    bot_env\Scripts\activate
    ```

2. Install dependencies
    ```bash
    pip install -r requirements.txt
    ```

3. Run from source
    ```bash
    python unlike_bot_gui.py
    ```

4. Compile for Windows (Must be run on a Windows machine)
    ```bash
    pyinstaller --onefile --noconsole --name InstagramMassUnlike-WindowsGUI unlike_bot_gui.py
    ```

5. Compile for Linux (Must be run on a Linux machine)
    ```bash
    pyinstaller --onefile --windowed --name InstagramMassUnlike-LinuxGUI unlike_bot_gui.py
    ```
