import platform
import os
import time

import pandas as pd
import numpy as np
import re

import cv2
import pytesseract

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service 
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)


class Crawler:
    def __init__(self):
        executable = ''

        if platform.system() == 'Windows':
            print('Detected OS : Windows')
            executable = './chromedriver-win64/chromedriver.exe'
        elif platform.system() == 'Linux':
            print('Detected OS : Linux')
            executable = './chromedriver-win64/chromedriver_linux'
        elif platform.system() == 'Darwin':
            print('Detected OS : Mac')
            executable = './chromedriver-win64/chromedriver_mac'
        else:
            raise OSError('Unknown OS Type')

        if not os.path.exists(executable):
            raise FileNotFoundError(
                'Chromedriver file should be placed at {}'.format(executable))

        service = Service(executable)
        self.driver = webdriver.Chrome(service = service)
        self.driver.set_window_position(0, 0)
        self.driver.set_window_size(1024, 768)
        browser_version = 'Failed to detect version'
        chromedriver_version = 'Failed to detect version'
        major_version_different = False

        if 'browserVersion' in self.driver.capabilities:
            browser_version = str(self.driver.capabilities['browserVersion'])

        if 'chrome' in self.driver.capabilities:
            if 'chromedriverVersion' in self.driver.capabilities['chrome']:
                chromedriver_version = str(
                    self.driver.capabilities['chrome']['chromedriverVersion']).split(' ')[0]

        if browser_version.split('.')[0] != chromedriver_version.split('.')[0]:
            major_version_different = True

        print('_________________________________')
        print('Current web-browser version:\t{}'.format(browser_version))
        print('Current chrome-driver version:\t{}'.format(chromedriver_version))
        if major_version_different:
            print('warning: Version different')
            print(
                'Download correct version at "http://chromedriver.chromium.org/downloads" and place in "./chromedriver"')
        print('_________________________________')
    
    def get_captcha(self):
        screenshot = self.driver.get_screenshot_as_png()
        # Chuyển đổi dữ liệu PNG thành mảng NumPy
        screenshot_array = np.frombuffer(screenshot, np.uint8)

        # Đọc hình ảnh từ mảng NumPy
        image = cv2.imdecode(screenshot_array, cv2.IMREAD_COLOR)
        resized_image = cv2.resize(image, (1920, 1080))

        # Cắt ảnh
        x1, y1, x2, y2 = (1035, 760, 1260, 840)
        crop = resized_image[y1:y2, x1:x2]    

        resized_image = cv2.resize(crop, (390, 150))
        blurred_image = cv2.cvtColor(resized_image, cv2.COLOR_BGR2GRAY)

        kernel = np.ones((6,6), np.uint8)
        dilation = cv2.dilate(blurred_image, kernel, iterations=1)

        for row in range(len(dilation)):
            for col in range(len(dilation[row])):
                if dilation[row, col] < 150:
                    dilation[row, col] = 0
                else:
                    dilation[row, col] = 255

        dilation = cv2.medianBlur(dilation, 5, 0)
        height, width = dilation.shape
        # Kích thước mới (tăng thêm 30 pixel ở dưới)
        new_height = height + 30
        new_width = width
        # Tạo một hình ảnh mới với kích thước mới và màu trắng
        new_image = np.zeros((new_height, new_width), dtype=np.uint8)
        new_image[:] = (255)  # Gán màu trắng (255, 255, 255)
        # Sao chép hình ảnh gốc vào hình ảnh mới
        new_image[:height, :] = dilation
        # Trích xuất văn bản từ hình ảnh
        text = pytesseract.image_to_string(new_image,nice = 20,config='--psm 13')
        #xóa các kí tự punctuation
        text = re.sub(r'[^\w\s]', '', text)
        # Loại bỏ các khoảng trắng thừa
        text = ''.join(text.split())
        return text
    
    def test_captcha(self, captcha):
        if len(captcha) != 5:
            return False
            
        url = f"https://www.gdt.gov.vn/TTHKApp/jsp/results.jsp?maTinh=805&maHuyen=80511&maXa=&hoTen=&kyLb=&diaChi=&maSoThue=&searchType=11&uuid=d01567b7-cb8b-47ae-b3b7-dfd6132076c4&captcha={captcha}&pageNumber=1"
        self.driver.get(url)
        element = self.driver.find_element(By.XPATH, '/html/body/div[1]')
        if element.text == "Vui lòng nhập đúng mã xác nhận.":
            return False
        self.driver.save_screenshot("screenshot.png")
        return True

    def reload_page(self):
        while True:
            self.driver.get("https://www.gdt.gov.vn/wps/portal/home/hct")
            time.sleep(1)
            captcha = self.get_captcha()
            
            if self.test_captcha(captcha):
                print(f"Captcha is correct:{captcha}")
                break
        return captcha 

    def crawl(self, ma_tinh, ma_huyen, ma_xa, search_types, ky_LB, captcha= None):
        search_types_html = {'11':'/html/body/div[4]/table',
                            '10':'/html/body/table',
                            '12':'/html/body/div[4]/table',
                            '03':'/html/body/div[4]/table',
                            '04':'/html/body/table'}
        
        ky_LB_encoded = ky_LB.replace("/", f"%2F")
        if captcha == None:
            captcha = self.reload_page()

        start_time_crawl = time.time()
        df = pd.DataFrame()

        page = 1
        while True:
            url = f"https://www.gdt.gov.vn/TTHKApp/jsp/results.jsp?maTinh={ma_tinh}&maHuyen={ma_huyen}&maXa={ma_xa}&kyLb={ky_LB_encoded}&searchType={search_types}&captcha={captcha}&pageNumber={page}"
            self.driver.get(url)

            notify_element = self.driver.find_element(By.XPATH, '/html/body/div[1]')
            if notify_element.text == "Không tìm thấy kết quả":
                break

            table_element = self.driver.find_element(By.XPATH, search_types_html[search_types])
            tables = pd.read_html(table_element.get_attribute("outerHTML"))
            if len(tables[0]) < 1:
                break
            tables[0]['mã_tỉnh'] = ma_tinh
            tables[0]['mã_huyện'] = ma_huyen
            tables[0]['mã_xã'] = ma_xa
            tables[0]['kỳ_lập_bộ'] = ky_LB
            tables[0]['search_type'] = search_types
            df = pd.concat([df, tables[0]])
            page += 1

        if search_types in ["11", "12", "03"]:
            df.columns = [x[0] + " " + x[1] if x[0] != x[1] else x[0] for x in df.columns]
        df.columns = [col.strip() for col in df.columns]
        
        search_types = int(search_types)
        ky_LB = pd.to_datetime(ky_LB).strftime('%Y-%m')

        save_path = f'./Crawled_Data_1/{ky_LB}/{ma_xa}_{search_types}_{ky_LB}.csv'
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        df.to_csv(save_path, index=False, encoding='utf-8-sig')
        print(f"Done {ma_xa}_{search_types}_{ky_LB}.csv")

        end_time_crawl = time.time()
        elapsed_time = end_time_crawl - start_time_crawl
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

        try:
            number_of_records = len(df)
            number_of_distinct_period = df["Kỳ lập bộ"].nunique()
            number_of_unique_tax_code = df['Mã số thuế'].nunique()
        except:
            number_of_records = 0
            number_of_distinct_period = 0
            number_of_unique_tax_code = 0

        task_description_1 = f"Task Crawl: {ma_xa} - Kỳ Lập Bộ: {ky_LB}"
        task_description_2 = f"Type: {search_types} - Number of records: {number_of_records} - Number of distinct period: {number_of_distinct_period} - Number of distinct tax code: {number_of_unique_tax_code} "
        log_message = f"{timestamp} - {task_description_1} - {elapsed_time:.2f} seconds - {task_description_2}\n"
        
        with open("log.txt", "a", encoding="utf-8") as log_file:
            log_file.write(log_message)
            log_file.close()

        time.sleep(1)


    def crawl_all(self, ky_LB):
        ds_xa = pd.read_csv('ds_full.csv')['maXa']
        search_types = ['11','10', '12', '03', '04']

        start_time = time.time()
        captcha = self.reload_page()

        for i in range(len(ds_xa)):
            maTinh = int(str(ds_xa[i])[:3])
            maHuyen = int(str(ds_xa[i])[:5])
            maXa = int(ds_xa[i])

            print('_________________________________')
            print('[{}/{}] Crawling {}'.format(i + 1, len(ds_xa), ds_xa[i]))
            
            for search in search_types:
                self.crawl(maTinh, maHuyen, maXa, search, ky_LB, captcha)
                end_time = time.time()
                elapsed_time = end_time - start_time
                if elapsed_time > 60:
                    print('Reload captcha')
                    captcha = self.reload_page()
                    start_time = time.time()
            print('[{}/{}] Done {}'.format(i + 1, len(ds_xa), ds_xa[i]))
            print('_________________________________')


if __name__ == "__main__":
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

    crawl = Crawler()
    ky_LB = '02/2019'
    crawl.crawl_all(ky_LB)
