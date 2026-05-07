"""Tarayıcı tespitini test et."""
from core.auth import detect_installed_browsers, list_browser_profiles


def main():
    print("=" * 50)
    print("Sistemde tespit edilen tarayıcılar:")
    print("=" * 50)
    browsers = detect_installed_browsers()
    if not browsers:
        print("❌ Hiç tarayıcı tespit edilmedi!")
    else:
        for b in browsers:
            print(f"  ✓ {b}")
            try:
                profiles = list_browser_profiles(b)
                for p in profiles:
                    print(f"    └─ profil: {p}")
            except Exception as e:
                print(f"    └─ profil listelenemedi: {e}")
    print("=" * 50)


if __name__ == "__main__":
    main()
