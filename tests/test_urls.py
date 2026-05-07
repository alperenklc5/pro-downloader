"""Site compatibility testi icin URL listesi.

Her URL'nin gercekten erisilebilir oldugundan emin ol.
URL'ler bozuldugunda bu listeyi guncelle.

Kategoriler:
- tier1: Public, cookie gerekmez
- tier2: Bazen cookie ister
- tier3: Cookie genellikle gerekli
- nsfw: Yetiskin icerik
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass
class TestURL:
    site: str
    url: str
    tier: Literal["tier1", "tier2", "tier3", "nsfw"]
    category: str  # "video-platform", "social", "adult", vb.
    notes: str = ""
    expected_min_duration: int = 1  # Beklenen min sure (saniye)


# === TIER 1: Mainstream, Public, Cookie Gerekmez ===
TIER_1_URLS = [
    TestURL(
        site="YouTube",
        url="https://www.youtube.com/watch?v=jNQXAC9IVRw",
        tier="tier1",
        category="video-platform",
        notes="Ilk YouTube videosu (Me at the zoo), her zaman erisilebilir",
    ),
    TestURL(
        site="YouTube Shorts",
        url="https://www.youtube.com/shorts/dQw4w9WgXcQ",
        tier="tier1",
        category="video-platform",
        notes="Rickroll, silinmesi cok dusuk ihtimal",
    ),
    TestURL(
        site="Vimeo",
        url="https://vimeo.com/259411563",
        tier="tier1",
        category="video-platform",
        notes="Vimeo Staff Pick, stabil",
    ),
    TestURL(
        site="Dailymotion",
        url="https://www.dailymotion.com/video/x5e9eog",
        tier="tier1",
        category="video-platform",
        notes="Dailymotion impersonate bagimliligina ihtiyac duyabilir (curl_cffi)",
    ),
    TestURL(
        site="TED",
        url="https://www.ted.com/talks/sir_ken_robinson_do_schools_kill_creativity",
        tier="tier1",
        category="video-platform",
        notes="TED Talk, kalici icerik",
    ),
    TestURL(
        site="Streamable",
        url="https://streamable.com/moo",
        tier="tier1",
        category="video-platform",
        notes="Streamable test videosu",
    ),
    TestURL(
        site="Bandcamp",
        url="https://musique.coeurdepirate.com/track/comme-des-enfants",
        tier="tier1",
        category="audio",
        notes="Audio-only test, Bandcamp destegi",
    ),
]

# === TIER 2: Bazen Cookie Ister ===
TIER_2_URLS = [
    TestURL(
        site="Twitter/X",
        url="https://twitter.com/elonmusk/status/1840836143437066620",
        tier="tier2",
        category="social",
        notes="Twitter yt-dlp destegi API degisiklikleriyle bozulabilir, URL'yi guncelle",
    ),
    TestURL(
        site="TikTok",
        url="https://www.tiktok.com/@scout2015/video/6718335390845095173",
        tier="tier2",
        category="social",
        notes="TikTok bot tespiti agresif, yt-dlp guncel olmali",
    ),
    TestURL(
        site="Facebook",
        url="https://www.facebook.com/watch/?v=10153231379946729",
        tier="tier2",
        category="social",
        notes="Public video, login bazen ister",
    ),
    TestURL(
        site="Instagram Reel",
        url="https://www.instagram.com/reel/CkE7jGSvFEq/",
        tier="tier2",
        category="social",
        notes="Public hesap reel'i",
    ),
]

# === TIER 3: Cookie Genellikle Gerekli ===
TIER_3_URLS = [
    TestURL(
        site="Instagram Story",
        url="https://www.instagram.com/stories/instagram/",
        tier="tier3",
        category="social",
        notes="Login zorunlu, takip ediliyor olmalisin",
    ),
    TestURL(
        site="Bilibili",
        url="https://www.bilibili.com/video/BV1xx411c7mD",
        tier="tier3",
        category="video-platform",
        notes="Cin sitesi, bazi icerikler bolgesel",
    ),
    TestURL(
        site="VK Video",
        url="https://vk.com/video-13895667_456239108",
        tier="tier3",
        category="social",
        notes="Rus sosyal medyasi",
    ),
]

# === NSFW: Yetiskin Icerik ===
NSFW_URLS = [
    TestURL(
        site="RedGifs",
        url="https://www.redgifs.com/watch/orangemoderntortoise",
        tier="nsfw",
        category="adult",
        notes="GIF tabanli, yt-dlp destekliyor",
    ),
    TestURL(
        site="Pornhub",
        url="https://www.pornhub.com/view_video.php?viewkey=ph5d8b8e8b8e8b8",
        tier="nsfw",
        category="adult",
        notes="Placeholder URL - gercek URL ile degistir",
    ),
    TestURL(
        site="Xvideos",
        url="https://www.xvideos.com/video.oomtcbv9ffb/wife_s_near_miss_lets_husband_getaway_with_his_tryst",
        tier="nsfw",
        category="adult",
        notes="Placeholder URL - gercek URL ile degistir",
    ),
    TestURL(
        site="xHamster",
        url="https://xhamster.com/videos/cheating-a-business-trip-with-a-co-worker-xhMwpBG",
        tier="nsfw",
        category="adult",
        notes="Placeholder URL - gercek URL ile degistir",
    ),
    TestURL(
        site="YouPorn",
        url="https://www.youporn.com/watch/190936831/",
        tier="nsfw",
        category="adult",
        notes="Placeholder URL - gercek URL ile degistir",
    ),
    TestURL(
        site="SpankBang",
        url="https://spankbang.com/9eb8v/video/enjoyx+colombian+girl+la+paisita+gets+her+tight+holes+inspected+by+a+tattooed+macho+guy",
        tier="nsfw",
        category="adult",
        notes="Placeholder URL - gercek URL ile degistir",
    ),
    TestURL(
        site="Eporner",
        url="https://www.eporner.com/video-PddKLDfrcoo/anal-romp-with-massive-boobs-latina-rough-romp-and-creampie/",
        tier="nsfw",
        category="adult",
        notes="Placeholder URL - gercek URL ile degistir",
    ),
]


def get_all_urls(tiers: list[str] | None = None) -> list[TestURL]:
    """Belirli tier'lerdeki URL'leri dondur. tiers=None -> hepsi."""
    all_urls = TIER_1_URLS + TIER_2_URLS + TIER_3_URLS + NSFW_URLS
    if tiers is None:
        return all_urls
    return [u for u in all_urls if u.tier in tiers]


# Kullanicinin kendi URL'lerini eklemesi icin
USER_CUSTOM_URLS: list[TestURL] = [
    # Buraya kendi test URL'lerini ekleyebilirsin
    # TestURL(site="Custom", url="https://...", tier="tier1", category="custom"),
]
