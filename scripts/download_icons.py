# -*- coding: utf-8 -*-
"""دانلود آیکون‌های Tabler (MIT) — مجموعه انتخابی برای آکادمی"""
import urllib.request, time, os

ICONS = """
home search user users shopping-cart heart star book book-2 video
certificate award medal school-bell school settings bell message-circle messages menu-2
x check chevron-left chevron-right chevron-down arrow-left arrow-right arrow-up arrow-down
phone mail map-pin clock play download upload edit trash plus minus filter grid
wallet credit-card coin gift percent shield shield-check lock eye eye-off logout
dashboard chart-bar chart-pie file-text folder send refresh sparkles globe
external-link question-mark info-circle alert-triangle flame target trophy
microphone headphones printer share copy link briefcase code database device-mobile
brand-telegram brand-instagram brand-whatsapp brand-youtube brand-github brand-linkedin
brand-x brand-facebook checklist clipboard notes pencil building-bank moneybag
piggy-bank report-money trending-up thumbs-up badge crown rocket bulb bookmark
layers palette key ticket calendar-event circle-check circle-x loader history
bookmarks library camera photo music headset live-view video-plus video-off
accessibility language direction-rtl direction-ltr user-star user-heart user-check
settings-2 adjustments sliders sun moon contrast brush color-swatch
mail-forward mailbox message-2 dots dots-vertical dots-horizontal grip
layout layout-grid layout-list layout-dashboard columns rows
mood-smile mood-happy mood-sad stickers smiley
package box archive tag tags price-tag discount
banknote cash receipt invoice report-analytics chart-line
file-zip file-code file-download file-upload file-copy folder-open
list-check list-numbers notes-off bookmarks-off pen-pencil
loader-2 rotate-clockwise zoom-in zoom-out
user-cancel user-circle user-cog user-edit user-hexagon user-plus user-search user-shield user-x users-group
home-2 home-heart home-search home-share home-star
graduation-cap briefcase certificate-2 medal-2
heart-pulse heart-rate-monitor first-aid-kit stethoscope
brand-python brand-react brand-vue brand-django brand-flask brand-git brand-docker brand-linux
playstation-x xbox-a video-3d headphones-filled music-pause music-play music-plus
presentation presentation-analytics map-2 map-pin-plus map-pins route flag flag-2 pin
building building-bank building-factory building-skyscraper buildings
cash-banknote cash-coin cash-register currency-dollar currency-euro currency-rial-iranian
moneybag-2 moneybag-3 moneybag-4 moneybag-5 moneybag-6 moneybag-7 moneybag-8 moneybag-9 moneybag-10
bolt bulb lamp flashlight torch
alarm clock-2 timer stopwatch hourglass
tag-filled star-filled heart-filled circle-check-filled circle-x-filled
calendar-plus calendar-minus calendar-check calendar-stats
shield-lock shield-check-filled shield-exclamation
arrow-big-left arrow-big-right arrow-big-down arrow-big-up arrows-sort sort-ascending sort-descending
playstation-circle video-2 video-4 presentation-chart
building-2 building-3 building-community building-hospital building-lighthouse building-mosque
building-tunnel building-warehouse building-wind-turbine building-castle
home-bolt home-check home-cog home-dollar home-down home-edit home-exclamation home-heart home-link home-lock home-minus home-move home-off home-plus home-question home-ribbon home-search home-share home-shield home-star home-up home-x
graduation-cap-2 briefcase-2 certificate-off
medal-2-off first-aid-kit-off
currency-rial currency-riyal currency-dollar-singapore currency-euro-off
bolt-off bulb-off bulb-filled bulb-auto bulb-2 bulb-3
alarm-off alarm-plus alarm-minus timer-off hourglass-off
clock-hour-3 clock-hour-9 clock-2-off
tag-off tags-off price-tag-off discount-2 percent-off
package-off box-2 box-3 cube sphere cylinder cone archive-off
banknote-off cash-off receipt-off invoice-off report-off
file-off file-x file-question file-alert file-shredder folder-off folder-x
list-x list-tree list-search list-details
mood-wink mood-confuzed mood-cry mood-angry mood-neutral
emoticon-happy emoticon-sad emoticon-neutral emoticon-laughing emoticon-wink
smiley-x smiley-wink smiley-sad smiley-happy smiley-neutral
headphones-off microphone-off music-off live-view-off presentation-off map-off
route-off sign-left sign-right signs-road parking traffic-cones flag-off flag-3 flag-check
pin-off pin-end pin-tick pin-tack pin-x
building-off buildings-off
lock-open lock-off key-off
settings-cog adjustments-horizontal toggle-left toggle-right
palette-off brush-off paint color-swatch-off
sun-high sunrise sunset moon-stars cloud cloud-rain cloud-snow wind wave
droplet droplet-half droplet-filled droplet-filled-2
fire-hydrant volcano tornado hurricane rainbow snowflake
""".split()

os.makedirs('static/icons', exist_ok=True)
ok, fail = 0, []
for name in ICONS:
    if not name.strip():
        continue
    url = f"https://cdn.jsdelivr.net/npm/@tabler/icons@3.31.0/icons/outline/{name}.svg"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        data = urllib.request.urlopen(req, timeout=20).read()
        if data.startswith(b'<svg'):
            open(f'static/icons/{name}.svg', 'wb').write(data)
            ok += 1
        else:
            fail.append(name)
    except Exception:
        fail.append(name)
    time.sleep(0.02)
print(f'دانلود: {ok} موفق، {len(fail)} ناموفق')
if fail:
    print('ناموفق:', ', '.join(fail))
