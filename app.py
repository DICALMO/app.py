from flask import Flask, request, jsonify, send_from_directory, render_template_string
import os
import requests
from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO
import zipfile
import base64
from flask import Flask
import threading
import os
from flask import Flask
from flask_cors import CORS

app = Flask(__name__)
CORS(app) 
@app.route('/download', methods=['GET'])
def download_chapter_images():
    title = request.args.get('title')
    chapter_raw = request.args.get('chapters')

    if not title or not chapter_raw:
        return jsonify({"success": False, "error": "Title and chapters are required"})

    try:
        chapters = []
        for part in chapter_raw.split(','):
            if '-' in part:
                start, end = map(int, part.split('-'))
                chapters.extend(range(start, end + 1))
            else:
                chapters.append(int(part))
    except ValueError:
        return jsonify({"success": False, "error": "Invalid chapter numbers format"})

    download_dir = 'Download'
    os.makedirs(download_dir, exist_ok=True)

    results = []
    base64_images = []

    for chapter in chapters:
        zip_filename = f"{title}_ch{chapter}.zip"
        zip_path = os.path.join(download_dir, zip_filename)

        with zipfile.ZipFile(zip_path, 'w') as zipf:
            url = f'https://azoramoon.com/series/{title}/{chapter}/?style=list'
            r = requests.get(url)
            soup = BeautifulSoup(r.content, "html.parser")
            images = soup.find_all('img', {'class': 'wp-manga-chapter-img'})
            
            if not images:
                results.append({"chapter": chapter, "success": False, "error": f"No images found"})
                continue

            chapter_images = []
            for idx, img_tag in enumerate(images):
                img_url = img_tag.get('src')
                if not img_url:
                    continue

                try:
                    img_data = requests.get(img_url).content
                    img = Image.open(BytesIO(img_data)).convert("RGB")
                    img_filename = f"{title}_ch{chapter}_p{idx + 1}.jpg"
                    img_path = os.path.join(download_dir, img_filename)
                    img.save(img_path)
                    zipf.write(img_path, arcname=img_filename)
                    os.remove(img_path)
                    
                    buffered = BytesIO()
                    img.save(buffered, format="JPEG")
                    img_str = base64.b64encode(buffered.getvalue()).decode('utf-8')
                    chapter_images.append(img_str)
                except Exception as e:
                    print(f"Error downloading image from chapter {chapter}: {e}")

            if chapter_images:
                results.append({
                    "chapter": chapter, 
                    "success": True, 
                    "link": f"/download/{zip_filename}", 
                    "view": f"/view/{title}/{chapter}"
                })

    if not results:
        return jsonify({"success": False, "error": "No chapters were downloaded"})

    return jsonify({
        "success": True,
        "results": results,
        "view": f"/view/{title}/{chapters[0]}" if results[0]['success'] else None
    })

@app.route('/view/<title>/<int:chapter>')
def view_chapter(title, chapter):
    url = f'https://azoramoon.com/series/{title}/{chapter}/?style=list'
    r = requests.get(url)
    soup = BeautifulSoup(r.content, "html.parser")
    images = soup.find_all('img', {'class': 'wp-manga-chapter-img'})
    
    image_urls = [img.get('src') for img in images if img.get('src')]
    
    return render_template_string(f"""
    <!DOCTYPE html>
    <html dir="rtl" lang="ar">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{title} - الفصل {chapter}</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                background-color: #121212;
                color: white;
                margin: 0;
                padding: 20px;
                text-align: center;
            }}
            .chapter-title {{
                color: #27ae60;
                margin-bottom: 20px;
            }}
            .manga-image {{
                max-width: 100%;
                height: auto;
                margin-bottom: 10px;
                box-shadow: 0 4px 8px rgba(0,0,0,0.3);
            }}
            .nav-buttons {{
                margin: 20px 0;
            }}
            .nav-button {{
                background: #27ae60;
                color: white;
                border: none;
                padding: 10px 20px;
                margin: 0 10px;
                border-radius: 5px;
                cursor: pointer;
                text-decoration: none;
            }}
        </style>
    </head>
    <body>
        <h1 class="chapter-title">{title} - الفصل {chapter}</h1>
        <div class="nav-buttons">
            <button class="nav-button" onclick="scrollToTop()">الأعلى</button>
            <button class="nav-button" onclick="scrollToBottom()">الأسفل</button>
        </div>
        {"".join([f'<img class="manga-image" src="{url}" alt="صفحة {i+1}">' for i, url in enumerate(image_urls)])}
        <div class="nav-buttons">
            <button class="nav-button" onclick="scrollToTop()">الأعلى</button>
            <button class="nav-button" onclick="scrollToBottom()">الأسفل</button>
        </div>
        <script>
            function scrollToTop() {{
                window.scrollTo({{top: 0, behavior: 'smooth'}});
            }}
            function scrollToBottom() {{
                window.scrollTo({{top: document.body.scrollHeight, behavior: 'smooth'}});
            }}
        </script>
    </body>
    </html>
    """)

@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory('Download', filename)

if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=5000)