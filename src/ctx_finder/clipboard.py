import sys
import subprocess
import shutil

def copy_to_clipboard(text: str) -> bool:
    """
    Copy text to system clipboard using OS-native CLI utilities.
    Returns True if copy succeeded, False otherwise.
    """
    platform = sys.platform
    
    try:
        if platform == "win32":
            if shutil.which("clip"):
                # Windows 'clip' command
                process = subprocess.Popen(['clip'], stdin=subprocess.PIPE, text=True)
                process.communicate(input=text)
                return process.returncode == 0
                
        elif platform == "darwin":
            if shutil.which("pbcopy"):
                # macOS 'pbcopy' command
                process = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE, text=True)
                process.communicate(input=text)
                return process.returncode == 0
                
        elif platform.startswith("linux"):
            # Check for xclip first, then xsel
            if shutil.which("xclip"):
                process = subprocess.Popen(['xclip', '-selection', 'clipboard'], stdin=subprocess.PIPE, text=True)
                process.communicate(input=text)
                return process.returncode == 0
            elif shutil.which("xsel"):
                process = subprocess.Popen(['xsel', '--clipboard', '--input'], stdin=subprocess.PIPE, text=True)
                process.communicate(input=text)
                return process.returncode == 0
                
    except Exception:
        pass
        
    return False
