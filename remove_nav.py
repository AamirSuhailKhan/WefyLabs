import os
import glob
import re

def main():
    dashboard_dir = r"c:\Users\aamir\OneDrive\Desktop\crm real state\apps\web\src\app\dashboard"
    files = glob.glob(os.path.join(dashboard_dir, "**", "page.tsx"), recursive=True)
    files.extend(glob.glob(os.path.join(dashboard_dir, "**", "layout.tsx"), recursive=True))
    files.append(r"c:\Users\aamir\OneDrive\Desktop\crm real state\apps\web\src\app\knowledge\page.tsx")

    for file_path in files:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        if "DashboardNav" in content:
            print(f"Modifying {file_path}")
            # Remove import
            content = re.sub(r"import\s+DashboardNav\s+from\s+['\"]@/components/shared/DashboardNav['\"];?\n?", "", content)
            
            # Remove <DashboardNav /> or <DashboardNav onAddLead={...} />
            content = re.sub(r"\s*<DashboardNav[^>]*/>\s*", "\n", content)
            
            # Write back
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

if __name__ == "__main__":
    main()
