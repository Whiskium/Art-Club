# 引入依赖库

import fitz, os, re, requests, time, zipfile

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import NoSuchElementException
from urllib.parse import unquote

# 配置 Selenium

os.environ["webdriver.chrome.driver"] = '/usr/bin/chromedriver'
option = webdriver.ChromeOptions()
option.add_argument('--headless') # 启用无头模式
option.add_argument('--incognito') # 启用无痕模式
pref = {"profile.default_content_setting_values.geolocation": 2}
option.add_experimental_option("prefs", pref) # 禁用地理位置
serv = Service("/usr/bin/chromedriver")

repo_tag_path = 'https://api.github.com/repos/' + os.environ.get('GITHUB_REPOSITORY') + '/tags'
lib = int(requests.get(repo_tag_path).json()[0]["name"])

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
            return time.time()
        filename = unquote(filename.encode('unicode_escape').decode('utf-8').replace('\\x', '%'))[1:-1]
        return filename
    global FILE_NAME_ZIP
    FILE_NAME_ZIP = get_file_name(file_requests)
    print('开始下载：' + FILE_NAME_ZIP)
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
            img_path = 'temp/' + imgs[i]
            img_doc = fitz.open(img_path)
            pdfbytes = img_doc.convert_to_pdf()
            imgpdf = fitz.open("pdf", pdfbytes)
            doc.insert_pdf(imgpdf)
            os.remove(img_path)
        global FILE_NAME_PDF
        FILE_NAME_PDF = zip_path[0:-4] + '.pdf'
        doc.save(FILE_NAME_PDF)
    os.rmdir('temp')
    print('转换完成：' + FILE_NAME_PDF)

# 获取更新情况

driver = webdriver.Chrome(options=option, service=serv) # 启动 Chrome 浏览器
# driver = webdriver.Edge() # 启动 Edge 浏览器

driver.get('https://comic-walker.com/contents/detail/KDCW_AM01000007010000_68/') # 跳转至 Comic Walker
element = driver.find_element(By.CLASS_NAME, 'comicIndex-title').text # 获取最新话字符串
new = int(re.findall(r'\d+', element)[0]) # 获取最新话
os.system('echo "pdfname=None" >> $GITHUB_OUTPUT')
if new > lib: # 如果有更新
    print('检测到原作更新：第 ' + str(new) + ' 话')
    driver.get(os.environ['SOURCE_URL'] + str(new)) # 跳转至资源站
    try: # 检查资源站是否更新
        print('正在前往资源站检测更新')
        url = driver.find_element(By.PARTIAL_LINK_TEXT, 'Download').get_attribute('href') # 获取下载链接
    except NoSuchElementException: # 资源站未更新
        print('资源站未更新')
        os.system('echo "flag=false" >> $GITHUB_OUTPUT')
    else: # 资源站已更新
        print('检测到资源更新')
        download_file(url)
        zip2pdf(FILE_NAME_ZIP)
        print('将文件发送至 Send 流程')
        os.system('echo "flag=true" >> $GITHUB_OUTPUT')
        os.system('echo "pdfname=%s" >> $GITHUB_OUTPUT' % FILE_NAME_PDF)
        os.system('echo "chapter=%d" >> $GITHUB_OUTPUT' % new)
else: # 如果无更新
    print('无更新')
    os.system('echo "flag=false" >> $GITHUB_OUTPUT')