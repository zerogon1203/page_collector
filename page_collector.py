#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Page Collector - 웹사이트 순회 및 마크다운 변환 도구
"""

import os
import re
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import html2text
from tqdm import tqdm
import json
from pathlib import Path


class PageCollector:
    def __init__(self, base_url, output_dir="output", delay=1):
        """
        페이지 수집기 초기화
        
        Args:
            base_url (str): 기본 URL
            output_dir (str): 출력 디렉토리
            delay (int): 요청 간 지연 시간 (초)
        """
        self.base_url = base_url
        self.output_dir = Path(output_dir)
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # 마크다운 변환기 설정
        self.h = html2text.HTML2Text()
        self.h.ignore_links = False
        self.h.ignore_images = False
        self.h.body_width = 0  # 줄바꿈 비활성화
        
        # 출력 디렉토리 생성
        self.output_dir.mkdir(exist_ok=True)
        
    def clean_filename(self, title):
        """파일명으로 사용할 수 있도록 문자열 정리"""
        # 특수문자 제거하고 공백을 언더스코어로 변경
        clean = re.sub(r'[^\w\s가-힣-]', '', title)
        clean = re.sub(r'\s+', '_', clean)
        return clean[:100]  # 파일명 길이 제한
    
    def extract_content(self, url):
        """URL에서 본문 내용 추출"""
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or 'utf-8'
            
            soup = BeautifulSoup(response.text, 'lxml')
            
            # 제목 추출
            title = soup.find('title')
            title_text = title.get_text().strip() if title else "제목없음"
            
            # article 태그를 우선적으로 찾기
            articles = soup.find_all('article')
            
            if articles:
                # 여러 article이 있는 경우 가장 큰 내용을 가진 것을 선택
                if len(articles) > 1:
                    content = max(articles, key=lambda x: len(x.get_text().strip()))
                    print(f"  - {len(articles)}개의 article 태그 발견, 가장 큰 것을 선택")
                else:
                    content = articles[0]
                    print(f"  - article 태그 발견")
            else:
                # article이 없는 경우 대안 선택자 시도
                content_selectors = [
                    'main', 
                    '.content',
                    '.post-content',
                    '.entry-content',
                    '#content',
                    '.main-content',
                    'body'
                ]
                
                for selector in content_selectors:
                    content = soup.select_one(selector)
                    if content and content.get_text().strip():
                        print(f"  - {selector} 선택자로 내용 발견")
                        break
                else:
                    # 모든 선택자로도 찾지 못한 경우
                    content = soup.find('body')
                    print(f"  - article 태그 없음, body 태그 사용")
            
            # 불필요한 요소 제거
            if content:
                # article 태그 내부의 불필요한 요소들 제거
                unwanted_tags = [
                    'script', 'style', 'nav', 'header', 'footer', 'aside',
                    '.md-nav', '.md-header', '.md-footer', '.md-sidebar',
                    '.md-tabs', '.md-tabs__list', '.md-tabs__item',
                    '.md-header__title', '.md-header__button',
                    '.md-footer__title', '.md-footer__link'
                ]
                
                for tag_name in ['script', 'style', 'nav', 'header', 'footer', 'aside']:
                    for tag in content.find_all(tag_name):
                        tag.decompose()
                
                # CSS 클래스로 지정된 불필요한 요소들 제거
                for class_name in ['.md-nav', '.md-header', '.md-footer', '.md-sidebar']:
                    for tag in content.select(class_name):
                        tag.decompose()
                
                print(f"  - 불필요한 요소 제거 완료")
            
            # HTML을 마크다운으로 변환
            if content:
                html_content = str(content)
                markdown_content = self.h.handle(html_content)
            else:
                markdown_content = "내용을 찾을 수 없습니다."
            
            return {
                'title': title_text,
                'url': url,
                'content': markdown_content,
                'status': 'success'
            }
            
        except Exception as e:
            return {
                'title': '오류 발생',
                'url': url,
                'content': f"오류: {str(e)}",
                'status': 'error'
            }
    
    def save_to_markdown(self, data, filename=None):
        """데이터를 마크다운 파일로 저장"""
        if not filename:
            filename = self.clean_filename(data['title']) + '.md'
        
        filepath = self.output_dir / filename
        
        # 마크다운 형식으로 구성
        markdown_content = f"""# {data['title']}

**URL:** {data['url']}
**상태:** {data['status']}
**수집일시:** {time.strftime('%Y-%m-%d %H:%M:%S')}

---

{data['content']}
"""
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        
        return filepath
    
    def collect_from_urls(self, urls):
        """URL 목록에서 순차적으로 페이지 수집"""
        results = []
        
        print(f"총 {len(urls)}개의 페이지를 수집합니다...")
        
        for i, url in enumerate(tqdm(urls, desc="페이지 수집 중")):
            print(f"\n[{i+1}/{len(urls)}] 수집 중: {url}")
            
            # 상대 URL을 절대 URL로 변환
            if not url.startswith(('http://', 'https://')):
                url = urljoin(self.base_url, url)
            
            # 페이지 내용 추출
            data = self.extract_content(url)
            
            # 마크다운 파일로 저장
            filename = f"{i+1:03d}_{self.clean_filename(data['title'])}.md"
            filepath = self.save_to_markdown(data, filename)
            
            results.append({
                'url': url,
                'title': data['title'],
                'status': data['status'],
                'filepath': str(filepath)
            })
            
            print(f"저장 완료: {filepath}")
            
            # 지연 시간
            if i < len(urls) - 1:  # 마지막이 아니면 대기
                time.sleep(self.delay)
        
        return results
    
    def save_summary(self, results):
        """수집 결과 요약 저장"""
        summary_file = self.output_dir / "collection_summary.json"
        
        summary = {
            'total_pages': len(results),
            'success_count': len([r for r in results if r['status'] == 'success']),
            'error_count': len([r for r in results if r['status'] == 'error']),
            'collection_time': time.strftime('%Y-%m-%d %H:%M:%S'),
            'results': results
        }
        
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        
        print(f"\n수집 요약 저장: {summary_file}")
        print(f"성공: {summary['success_count']}개, 실패: {summary['error_count']}개")


def load_config_from_file(config_file):
    """JSON 설정 파일에서 설정 로드"""
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        return config
    except Exception as e:
        print(f"설정 파일 로드 오류: {e}")
        return None


def main():
    """메인 실행 함수"""
    print("=== Page Collector ===")
    print("웹사이트 순회 및 마크다운 변환 도구\n")
    
    # 설정 파일 사용 여부 확인
    use_config = input("설정 파일을 사용하시겠습니까? (y/N): ").strip().lower()
    
    if use_config in ['y', 'yes']:
        config_file = input("설정 파일 경로 (기본값: config.json): ").strip()
        if not config_file:
            config_file = "config.json"
        
        config = load_config_from_file(config_file)
        if not config:
            print("설정 파일을 불러올 수 없습니다. 수동 입력 모드로 전환합니다.\n")
        else:
            base_url = config.get('base_url', '')
            urls = config.get('urls', [])
            delay = config.get('delay', 1)
            output_dir = config.get('output_dir', 'output')
            
            if not base_url or not urls:
                print("설정 파일에 base_url과 urls가 필요합니다.")
                return
                
            print(f"설정 파일에서 로드된 정보:")
            print(f"- 기본 URL: {base_url}")
            print(f"- 출력 디렉토리: {output_dir}")
            print(f"- 지연 시간: {delay}초")
            print(f"- 수집할 페이지 수: {len(urls)}개\n")
            
            # 수집기 생성 및 실행
            collector = PageCollector(base_url, output_dir=output_dir, delay=delay)
            results = collector.collect_from_urls(urls)
            collector.save_summary(results)
            
            print(f"\n수집 완료! 결과는 '{collector.output_dir}' 디렉토리에 저장되었습니다.")
            return
    
    # 수동 입력 모드
    base_url = input("기본 URL을 입력하세요: ").strip()
    if not base_url:
        print("오류: 기본 URL이 필요합니다.")
        return
    
    print("\n순회할 링크들을 입력하세요 (한 줄에 하나씩, 빈 줄로 종료):")
    urls = []
    while True:
        url = input().strip()
        if not url:
            break
        urls.append(url)
    
    if not urls:
        print("오류: 최소 하나의 URL이 필요합니다.")
        return
    
    # 지연 시간 설정
    delay = input("요청 간 지연 시간(초, 기본값 1): ").strip()
    try:
        delay = int(delay) if delay else 1
    except ValueError:
        delay = 1
    
    # 수집기 생성 및 실행
    collector = PageCollector(base_url, delay=delay)
    results = collector.collect_from_urls(urls)
    collector.save_summary(results)
    
    print(f"\n수집 완료! 결과는 '{collector.output_dir}' 디렉토리에 저장되었습니다.")


if __name__ == "__main__":
    main()
