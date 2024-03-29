# 引入依赖库

import fitz, os, re, requests, zipfile

from datetime import datetime
from pytz import timezone

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import NoSuchElementException

from urllib.parse import unquote

from webdriver_manager.chrome import ChromeDriverManager

# 定义下载函数

def download_file(url):
    file_requests = requests.get(url, stream=True)
    def get_file_name(file_requests):
        headers = file_requests.headers
        if 'Content-Disposition' in headers and headers['Content-Disposition']:
            disposition_split = headers['Content-Disposition'].split(';')
            if len(disposition_split) > 1:
                if disposition_split[1].strip().lower().startswith('filename='):
                    file_name = disposition_split[1].split('=')
                    if len(file_name) > 1:
                        filename = unquote(file_name[1])
        if not filename and os.path.basename(file_requests):
            filename = os.path.basename(file_requests).split('?')[0]
        if not filename:
            return datetime.now(timezone('Asia/Shanghai')).strftime('%Y%m%d%H%M%S')
        filename = unquote(filename.encode('unicode_escape').decode('utf-8').replace('\\x', '%'))[1:-1]
        return filename
    global FILE_NAME_ZIP
    FILE_NAME_ZIP = get_file_name(file_requests)
    print(f'开始下载：{ FILE_NAME_ZIP }')
    with open(FILE_NAME_ZIP, 'wb') as f:
        for chunk in file_requests.iter_content(chunk_size=1024):
            if chunk:
                f.write(chunk)
    print('下载完成')

# 定义转换为 PDF 函数

def zip2pdf(zip_path):
    print('开始将文件转换为 PDF')
    os.makedirs('temp')
    with zipfile.ZipFile(zip_path) as zip:
        zip.extractall('temp')
    imgs = os.listdir('temp')
    imgs.sort(key=lambda x:int(re.search(r'^\d+(?=\.)', x).group()))
    imgs.reverse()
    with fitz.open() as doc:
        for i in range(len(imgs)):
            img_path = f'temp/{ imgs[i] }'
            img_doc = fitz.open(img_path)
            pdfbytes = img_doc.convert_to_pdf()
            imgpdf = fitz.open("pdf", pdfbytes)
            doc.insert_pdf(imgpdf)
            os.remove(img_path)
        global FILE_NAME_PDF
        FILE_NAME_PDF = f'{ zip_path[0:-4] }.pdf'
        doc.save(FILE_NAME_PDF)
    os.rmdir('temp')
    print(f'转换完成：{ FILE_NAME_PDF }')

# 配置 Selenium

options = webdriver.ChromeOptions()
options.add_argument('--headless') # 启用无头模式
options.add_argument('--incognito') # 启用无痕模式
pref = {"profile.default_content_setting_values.geolocation": 2}
options.add_experimental_option("prefs", pref) # 禁用地理位置
service = Service(ChromeDriverManager().install())

RepoTagPath = f'https://api.github.com/repos/{ os.environ.get("GITHUB_REPOSITORY") }/tags'
lib = int(requests.get(RepoTagPath).json()[0]["name"])

driver = webdriver.Chrome(options, service) # 启动 Chrome 浏览器
# driver = webdriver.Edge() # 启动 Edge 浏览器

# 获取更新情况

driver.get('https://comic-walker.com/contents/detail/KDCW_AM01000007010000_68/') # 跳转至 Comic Walker
element = driver.find_element(By.CLASS_NAME, 'comicIndex-title').text # 获取最新话字符串
MANGA_CHAPTER = int(re.findall(r'\d+', element)[0]) # 获取最新话
os.system('echo "MANGA_PDFNAME=None" >> $GITHUB_OUTPUT')
if MANGA_CHAPTER > lib: # 如果有更新
    print(f'检测到原作更新：第 { str(MANGA_CHAPTER) } 话')
    driver.get(os.environ['SOURCE_URL'] + str(MANGA_CHAPTER)) # 跳转至资源站
    try: # 检查资源站是否更新
        print('正在前往资源站检测更新')
        url = driver.find_element(By.PARTIAL_LINK_TEXT, 'Download').get_attribute('href') # 获取下载链接
    except NoSuchElementException: # 资源站未更新
        print('资源站未更新')
        os.system('echo "UPDATE_FLAG=False" >> $GITHUB_OUTPUT')
    else: # 资源站已更新
        print('检测到资源更新')
        download_file(url)
        zip2pdf(FILE_NAME_ZIP)
        print('将文件发送至 Send 流程')
        EMAIL_DATE = datetime.now(timezone('Asia/Shanghai')).strftime('%Y.%m.%d')
        os.system('echo "UPDATE_FLAG=True" >> $GITHUB_OUTPUT')
        os.system('echo "MANGA_CHAPTER=%d" >> $GITHUB_OUTPUT' % MANGA_CHAPTER)
        os.system('echo "MANGA_PDFNAME=%s" >> $GITHUB_OUTPUT' % FILE_NAME_PDF)
        os.system('echo "EMAIL_DATE=%d" >> $GITHUB_OUTPUT' % EMAIL_DATE)
else: # 如果无更新
    print('无更新')
    os.system('echo "UPDATE_FLAG=False" >> $GITHUB_OUTPUT')