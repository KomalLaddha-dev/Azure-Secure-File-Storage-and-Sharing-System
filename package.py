"""
Cross-platform packaging script for Azure App Service Linux.
Guarantees standard POSIX forward slashes ('/') in ZIP archives,
preventing the Windows backslash ('\\') TemplateNotFound bug on Linux Kudu.
"""
import os
import zipfile

def build_deployment_package():
    zip_path = "deploy.zip"
    files_to_include = [
        "app.py",
        "wsgi.py",
        "azure_storage.py",
        "auth.py",
        "config.py",
        "requirements.txt",
        "startup.txt"
    ]
    directories_to_include = ["static", "templates"]

    print("[*] Building Linux-compatible deploy.zip...")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        # Add root files
        for filename in files_to_include:
            if os.path.exists(filename):
                print(f" -> Adding root file: {filename}")
                zipf.write(filename, arcname=filename)
            else:
                print(f" [!] Warning: File {filename} not found!")

        # Add directories with explicit forward slashes ('/')
        for dirname in directories_to_include:
            for root, _, filenames in os.walk(dirname):
                for filename in filenames:
                    file_path = os.path.join(root, filename)
                    # Convert Windows backslashes to Linux forward slashes
                    posix_arcname = file_path.replace("\\", "/")
                    print(f" -> Adding {posix_arcname}")
                    zipf.write(file_path, arcname=posix_arcname)

    print(f"[+] Successfully generated {zip_path} ({os.path.getsize(zip_path)} bytes)")

if __name__ == "__main__":
    build_deployment_package()
