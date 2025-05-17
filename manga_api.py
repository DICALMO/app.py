import re
import time
import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import os

# === إعدادات الخادم والثوابت ===
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'ar,en-US;q=0.9,en;q=0.8',
    'Referer': 'https://lekmanga.net/',
    'DNT': '1'
}

# === تهيئة تطبيق Flask ===
app = Flask(__name__)
CORS(app)

# === الفئة المسؤولة عن تحميل المانجا ===
class MangaDownloader:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        
    def close(self):
        self.session.close()

    @staticmethod
    def slugify(text):
        text = text.lower().strip()
        text = re.sub(r'[\s_]+', '-', text)
        text = re.sub(r'[^a-z0-9-ء-ي]', '', text)
        text = re.sub(r'-+', '-', text)
        return text[:100]

    def download_content(self, url):
        """تحميل المحتوى العادي بدون إعادة محاولات"""
        try:
            response = self.session.get(url, timeout=20)
            response.raise_for_status()
            return response.text
        except Exception as e:
            self.log_error(f"فشل التحميل: {url} | الخطأ: {str(e)}")
            return None

    def fetch_chapter_images(self, title, chapter):
        base_urls = [
            f"https://lekmanga.net/manga/{self.slugify(title)}/{chapter}/",
            f"https://3asq.org/manga/{self.slugify(title)}/{chapter}/",
            f"https://azoramoon.com/series/{self.slugify(title)}/{chapter}/"
        ]

        for base_url in base_urls:
            self.log_info(f"جرب جلب الصور من: {base_url}")
            
            content = self.download_content(base_url)
            if not content:
                continue

            soup = BeautifulSoup(content, "html.parser")
            images = []
            
            img_elements = soup.find_all("img", class_=re.compile(r"wp-manga-chapter-img|chapter-img|manga-img"))

            for idx, img in enumerate(img_elements):
                img_url = None
                for attr in ['data-src', 'src', 'data-lazy-src', 'data-original']:
                    temp_url = img.get(attr)
                    if temp_url:
                        if temp_url.startswith(('http://', 'https://')):
                            img_url = temp_url
                        elif temp_url.startswith('//'):
                            img_url = f"https:{temp_url}"
                        elif temp_url.startswith('/'):
                            domain = re.match(r'https?://[^/]+', base_url).group()
                            img_url = f"{domain}{temp_url}"
                        break
                
                if img_url:
                    images.append((idx, img_url))

            if images:
                verified_images = self.verify_images(images)
                if verified_images:
                    self.log_info(f"تم العثور على {len(verified_images)} صور للفصل {chapter} من {base_url}")
                    return verified_images

        self.log_warning(f"لم يتم العثور على صور في الفصل: {chapter}")
        return None

    def verify_images(self, images):
        """تحقق من الصور بشكل متزامن وعادي"""
        verified = []
        for idx, url in images:
            try:
                response = self.session.head(url, timeout=10)
                if response.status_code == 200 and 'image' in response.headers.get('Content-Type', ''):
                    verified.append((idx, url))
            except Exception:
                continue
        return verified

    def log_info(self, message):
        print(f"[INFO] {time.ctime()} - {message}")

    def log_warning(self, message):
        print(f"[WARNING] {time.ctime()} - {message}")

    def log_error(self, message):
        print(f"[ERROR] {time.ctime()} - {message}")
        with open("error_log.txt", "a", encoding="utf-8") as f:
            f.write(f"{time.ctime()} - {message}\n")

# === تهيئة الكائن الرئيسي ===
manga_downloader = MangaDownloader()

# === نقاط نهاية Flask ===
@app.route('/')
def serve_index():
    return send_from_directory(os.path.dirname(os.path.abspath(__file__)), 'index.html')

@app.route('/get_chapter', methods=['GET'])
def get_chapter():
    title = request.args.get('title')
    chapter = request.args.get('chapter')
    
    if not title or not chapter:
        return jsonify({"error": "يجب توفير اسم المانجا ورقم الفصل"}), 400
    
    try:
        chapter = int(chapter)
    except ValueError:
        return jsonify({"error": "رقم الفصل يجب أن يكون رقماً صحيحاً"}), 400

    images_data = manga_downloader.fetch_chapter_images(title, chapter)
    
    if not images_data:
        return jsonify({"error": "لم يتم العثور على الفصل"}), 404
    
    ordered_images = [url for _, url in sorted(images_data, key=lambda x: x[0])]
    
    return jsonify({
        "title": title,
        "chapter": chapter,
        "images": ordered_images,
        "status": "success"
    })

@app.route('/health')
def health_check():
    return jsonify({"status": "healthy"})

@app.teardown_appcontext
def shutdown_session(exception=None):
    manga_downloader.close()

if __name__ == "__main__":
    print("GO AND FLASK")
    app.run(host="0.0.0.0", port=5000)