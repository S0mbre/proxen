
# What is proxen?

**proxen** is a small GUI tool to configure the web proxy settings on your system. Written completely in Python and relying on Qt5/6 for GUI, it works on any OS: Windows, Linux and Mac.

**proxen** will let you:
- set separate configurations for HTTP, HTTPS, FTP and RSYNC proxies
- enable / disable the top-layer system proxy (HTTP) with a single click
- automatically synchronize the proxy system environment variables (`HTTP_PROXY`, `HTTPS_PROXY`, `FTP_PROXY` and `RSYNC_PROXY`)
- persist the proxy settings across system reboots by writing to the underlying system files
- save / load proxy settings to / from JSON files
- review and manually edit system-wide and user environment variables (not only proxy-related!)
- keep a detailed debug log
- view comprehensive docs

# Installation

### 1. Clone repo
```
git clone https://github.com/S0mbre/proxen.git .
```

You can also download a release from `https://github.com/S0mbre/proxen/releases`

### 2. Install required packages

**proxen** runs on Python 3.9+, so please make sure you have one.

Then install the required Python packages (you may want to use `venv` to set up a virtual environment for Python first).
```
cd proxen
pip install -r requirements.txt
```

Before doing this, you can also pre-configure `requirements.txt` to choose the Qt distro of your choice: 
- PySide6 (*default*)
- PySide2
- PyQt6
- PyQt5

Apart from Qt, the `platform` package will be installed.

You are done!

# Updating

If you cloned the repo from GitHub, use git to pull the latest version:
```
cd proxen
git pull origin main
git checkout main
```

If you downloaded a ZIP release, go to `https://github.com/S0mbre/proxen/releases` to get a more recent one.

# Usage

The user interface is very intuitive.

### Enable / disable proxy with a single click
![](/resources/screen_01.png)

### Configure different proxies
![](/resources/screen_02.png)

### App settings
![](/resources/screen_03.png)

### Getting help
![](/resources/screen_04.png)

### Manual environment variable editing

Go to `Settings` page and press the `Env variables` button.

Edit environment variables directly in the table, add and delete using the actions in the righthand panel.

![](/resources/screen_05.png)
