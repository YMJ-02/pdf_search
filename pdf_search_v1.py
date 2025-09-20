"""
📚 PDF Search v1.0 - AI 기반 PDF 검색 도구 (최종 완성본)

✨ 주요 기능:
- 🤖 AI 기반 의미 검색 (sentence-transformers)
- 📄 PDF 문서 자동 텍스트 추출 및 인덱싱
- 🎯 실시간 유사도 표시 (0-100%)
- 📱 드래그 앤 드롭 파일 추가
- 🔍 2패널 레이아웃 (컨트롤 + 결과)
- 🎨 다크 테마 최적화
- ⚡ 멀티스레딩으로 빠른 처리
- 📊 실시간 진행률 표시

🛠️ 개발자: GitHub Copilot
📅 최종 완성: 2025년 9월 20일
🏷️ 버전: v1.0 (Production Ready)
"""

import sys
import os
import time
from pathlib import Path
from typing import List, Tuple, Optional

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QListWidget, QListWidgetItem,
    QTextEdit, QFileDialog, QFrame, QSplitter, QProgressBar,
    QScrollArea
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QDragEnterEvent, QDropEvent

# PDF 텍스트 추출을 위한 라이브러리
try:
    import PyPDF2
except ImportError:
    print("⚠️  PyPDF2가 설치되지 않았습니다. pip install PyPDF2로 설치해주세요.")
    sys.exit(1)

from memory_optimized_fix import MemoryEfficientDocumentIndex

class ModernTheme:
    """현대적인 어두운 테마"""
    
    # 메인 색상
    BACKGROUND = "#1e1e1e"
    PANEL_BG = "#252526"
    CARD_BG = "#2d2d30"
    
    # 텍스트
    TEXT_PRIMARY = "#cccccc"
    TEXT_SECONDARY = "#969696"
    TEXT_ACCENT = "#4fc3f7"
    
    # 액센트
    PRIMARY = "#0e7490"
    PRIMARY_HOVER = "#0891b2"
    SUCCESS = "#16a085"
    WARNING = "#f39c12"
    ERROR = "#e74c3c"
    
    # UI 요소
    BORDER = "#3c3c3c"
    HIGHLIGHT = "#007acc"
    SHADOW = "rgba(0, 0, 0, 0.3)"
    
    @classmethod
    def button_style(cls, bg_color=None, hover_color=None):
        """공통 버튼 스타일"""
        bg = bg_color or cls.PRIMARY
        hover = hover_color or cls.PRIMARY_HOVER
        return f"""
            QPushButton {{
                background-color: {bg};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 12px 16px;
                font-weight: bold;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {hover};
            }}
            QPushButton:disabled {{
                background-color: {cls.BORDER};
                color: {cls.TEXT_SECONDARY};
            }}
        """
    
    @classmethod
    def frame_style(cls, bg_color=None):
        """공통 프레임 스타일"""
        bg = bg_color or cls.CARD_BG
        return f"""
            QFrame {{
                background-color: {bg};
                border: 1px solid {cls.BORDER};
                border-radius: 8px;
                padding: 16px;
            }}
        """
    
    @classmethod
    def progress_bar_style(cls, color=None):
        """공통 프로그레스 바 스타일"""
        color = color or cls.PRIMARY
        return f"""
            QProgressBar {{
                border: 1px solid {cls.BORDER};
                border-radius: 6px;
                background-color: {cls.BACKGROUND};
                height: 10px;
                text-align: center;
            }}
            QProgressBar::chunk {{
                background-color: {color};
                border-radius: 6px;
            }}
        """

class DragDropArea(QFrame):
    """드래그 앤 드롭 영역"""
    files_dropped = pyqtSignal(list)
    
    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setup_ui()
    
    def setup_ui(self):
        self.setMinimumHeight(150)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {ModernTheme.PANEL_BG};
                border: 2px dashed {ModernTheme.BORDER};
                border-radius: 12px;
                color: {ModernTheme.TEXT_SECONDARY};
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 아이콘과 텍스트
        icon_label = QLabel("📁")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet("font-size: 40px; margin: 8px;")  # 크기 조정
        
        text_label = QLabel("PDF 파일을 이곳에 끌어다 놓으세요")
        text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text_label.setStyleSheet(f"""
            font-size: 16px;
            font-weight: bold;
            color: {ModernTheme.TEXT_SECONDARY};
            margin: 8px;
        """)
        
        sub_label = QLabel("또는 아래 버튼을 클릭하세요")
        sub_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub_label.setStyleSheet(f"""
            font-size: 12px;
            color: {ModernTheme.TEXT_SECONDARY};
            margin: 4px;
        """)
        
        layout.addWidget(icon_label)
        layout.addWidget(text_label)
        layout.addWidget(sub_label)
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.accept()
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: {ModernTheme.CARD_BG};
                    border: 2px dashed {ModernTheme.PRIMARY};
                    border-radius: 12px;
                    color: {ModernTheme.PRIMARY};
                }}
            """)
        else:
            event.ignore()
    
    def dragLeaveEvent(self, event):
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {ModernTheme.PANEL_BG};
                border: 2px dashed {ModernTheme.BORDER};
                border-radius: 12px;
                color: {ModernTheme.TEXT_SECONDARY};
            }}
        """)
    
    def dropEvent(self, event: QDropEvent):
        files = []
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if file_path.lower().endswith('.pdf'):
                files.append(file_path)
        
        if files:
            self.files_dropped.emit(files)
        
        self.dragLeaveEvent(event)
        event.accept()

class FileListWidget(QWidget):
    """파일 목록 위젯 - 단순 텍스트 리스트"""
    file_removed = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.files = []
        self.setup_ui()
    
    def setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(8)
        
        # 제목
        title = QLabel("📄 분석할 파일 목록")
        title.setStyleSheet(f"""
            color: {ModernTheme.TEXT_PRIMARY};
            font-size: 14px;
            font-weight: bold;
            margin: 8px 0;
        """)
        self.layout.addWidget(title)
        
        # 단순 리스트 위젯
        self.file_list_widget = QListWidget()
        self.file_list_widget.setStyleSheet(f"""
            QListWidget {{
                background-color: {ModernTheme.PANEL_BG};
                border: 1px solid {ModernTheme.BORDER};
                border-radius: 6px;
                outline: none;
                font-size: 12px;
                font-family: 'Segoe UI', Arial, sans-serif;
            }}
            QListWidget::item {{
                padding: 10px 12px;
                border-bottom: 1px solid {ModernTheme.BORDER};
                color: {ModernTheme.TEXT_PRIMARY};
                min-height: 20px;
                max-height: 20px;
            }}
            QListWidget::item:hover {{
                background-color: {ModernTheme.CARD_BG};
            }}
            QListWidget::item:selected {{
                background-color: {ModernTheme.PRIMARY};
                color: white;
            }}
        """)
        self.file_list_widget.setFixedHeight(200)  # 고정 높이로 설정
        self.file_list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.file_list_widget.customContextMenuRequested.connect(self.show_context_menu)
        
        self.layout.addWidget(self.file_list_widget)
    
    def add_files(self, file_paths: List[str]):
        for file_path in file_paths:
            if file_path not in self.files:
                self.files.append(file_path)
                self.add_file_item(file_path)
    
    def add_file_item(self, file_path: str):
        filename = Path(file_path).name
        
        # 파일명이 길면 줄임 처리
        if len(filename) > 40:
            display_name = f"📄 {filename[:37]}..."
        else:
            display_name = f"📄 {filename}"
        
        item = QListWidgetItem(display_name)
        item.setData(Qt.ItemDataRole.UserRole, file_path)
        
        # 툴팁 설정
        tooltip_text = f"""파일명: {filename}
경로: {file_path}
크기: {self.get_file_size(file_path)}

우클릭하여 제거할 수 있습니다."""
        item.setToolTip(tooltip_text)
        
        self.file_list_widget.addItem(item)
    
    def show_context_menu(self, position):
        """우클릭 메뉴"""
        item = self.file_list_widget.itemAt(position)
        if item:
            from PyQt6.QtWidgets import QMenu
            
            menu = QMenu(self)
            menu.setStyleSheet(f"""
                QMenu {{
                    background-color: {ModernTheme.CARD_BG};
                    border: 1px solid {ModernTheme.BORDER};
                    border-radius: 6px;
                    padding: 4px;
                }}
                QMenu::item {{
                    color: {ModernTheme.TEXT_PRIMARY};
                    padding: 8px 16px;
                    border-radius: 4px;
                }}
                QMenu::item:selected {{
                    background-color: {ModernTheme.PRIMARY};
                }}
            """)
            
            remove_action = menu.addAction("🗑️ 목록에서 제거")
            
            action = menu.exec(self.file_list_widget.mapToGlobal(position))
            if action == remove_action:
                file_path = item.data(Qt.ItemDataRole.UserRole)
                self.remove_file(file_path, item)
    
    def remove_file(self, file_path: str, item: QListWidgetItem):
        self.files.remove(file_path)
        row = self.file_list_widget.row(item)
        self.file_list_widget.takeItem(row)
        self.file_removed.emit(file_path)
    
    def get_file_size(self, file_path: str) -> str:
        """파일 크기 계산"""
        try:
            size = os.path.getsize(file_path)
            return f"{size / (1024 * 1024):.1f} MB" if size >= 1024 * 1024 else f"{size / 1024:.1f} KB" if size >= 1024 else f"{size} bytes"
        except:
            return "알 수 없음"
    
    def clear_files(self):
        self.files.clear()
        self.file_list_widget.clear()

class ResultCard(QFrame):
    """검색 결과 카드"""
    card_clicked = pyqtSignal(dict)
    
    def __init__(self, content: str, similarity: float, doc_info: dict):
        super().__init__()
        self.content = content
        self.similarity = similarity
        self.doc_info = doc_info
        self.setup_ui()
    
    def setup_ui(self):
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {ModernTheme.CARD_BG};
                border: 1px solid {ModernTheme.BORDER};
                border-radius: 8px;
                padding: 16px;
                margin: 8px;
            }}
            QFrame:hover {{
                border-color: {ModernTheme.PRIMARY};
                background-color: {ModernTheme.PANEL_BG};
            }}
        """)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # 상단: 파일 정보와 유사도
        header_layout = QHBoxLayout()
        
        # 파일 정보
        filename = Path(self.doc_info.get('file_path', '')).name
        page_num = self.doc_info.get('page_num', 0)
        file_info = QLabel(f"📄 {filename} (p.{page_num})")
        file_info.setStyleSheet(f"""
            color: {ModernTheme.TEXT_PRIMARY};
            font-weight: bold;
            font-size: 13px;
        """)
        
        # 유사도 표시
        similarity_widget = self.create_similarity_widget()
        
        header_layout.addWidget(file_info)
        header_layout.addStretch()
        header_layout.addWidget(similarity_widget)
        
        layout.addLayout(header_layout)
        
        # 내용 미리보기
        preview = self.content[:200] + "..." if len(self.content) > 200 else self.content
        content_label = QLabel(preview)
        content_label.setStyleSheet(f"""
            color: {ModernTheme.TEXT_SECONDARY};
            font-size: 12px;
            line-height: 1.4;
        """)
        content_label.setWordWrap(True)
        content_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        layout.addWidget(content_label)
        
        # 하단: 심플한 클릭 안내
        action_layout = QHBoxLayout()
        action_layout.setContentsMargins(0, 8, 0, 0)
        
        # 클릭 안내 텍스트
        click_hint = QLabel("� 카드를 클릭하면 PDF가 열립니다")
        click_hint.setStyleSheet(f"""
            QLabel {{
                color: {ModernTheme.TEXT_SECONDARY};
                font-size: 10px;
                font-style: italic;
                padding: 4px 0;
            }}
        """)
        click_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        action_layout.addWidget(click_hint)
        layout.addLayout(action_layout)
    
    def create_similarity_widget(self) -> QWidget:
        """유사도 시각화 위젯 - 더 명확하고 시각적"""
        container = QWidget()
        container.setFixedSize(100, 28)
        
        layout = QHBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)
        
        # 유사도에 따른 색상, 텍스트, 아이콘 결정
        similarity_percent = int(self.similarity * 100)
        
        if self.similarity >= 0.9:
            bg_color = "#27ae60"  # 진한 초록
            text_color = "white"
            grade = "최고"
            icon = "🔥"
            border_color = "#219a52"
        elif self.similarity >= 0.8:
            bg_color = "#2ecc71"  # 초록
            text_color = "white"
            grade = "우수"
            icon = "⭐"
            border_color = "#27ae60"
        elif self.similarity >= 0.7:
            bg_color = "#f39c12"  # 주황
            text_color = "white"
            grade = "좋음"
            icon = "👍"
            border_color = "#e67e22"
        elif self.similarity >= 0.6:
            bg_color = "#e67e22"  # 진한 주황
            text_color = "white"
            grade = "보통"
            icon = "📝"
            border_color = "#d35400"
        else:
            bg_color = "#95a5a6"  # 회색
            text_color = "white"
            grade = "낮음"
            icon = "📄"
            border_color = "#7f8c8d"
        
        # 컨테이너 스타일
        container.setStyleSheet(f"""
            QWidget {{
                background-color: {bg_color};
                border: 2px solid {border_color};
                border-radius: 14px;
            }}
        """)
        
        # 아이콘
        icon_label = QLabel(icon)
        icon_label.setStyleSheet(f"""
            QLabel {{
                font-size: 14px;
                color: {text_color};
                background: transparent;
                border: none;
            }}
        """)
        icon_label.setFixedSize(18, 18)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # 유사도 텍스트
        similarity_label = QLabel(f"{similarity_percent}%")
        similarity_label.setStyleSheet(f"""
            QLabel {{
                color: {text_color};
                font-weight: bold;
                font-size: 12px;
                background: transparent;
                border: none;
                padding: 0;
                margin: 0;
            }}
        """)
        similarity_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(icon_label)
        layout.addWidget(similarity_label)
        
        # 툴팁 설정
        container.setToolTip(f"""유사도: {similarity_percent}% ({grade})
이 결과가 검색어와 얼마나 관련이 있는지를 나타냅니다.

🔥 90% 이상: 최고 - 매우 정확한 결과
⭐ 80-89%: 우수 - 높은 관련성
👍 70-79%: 좋음 - 관련성 있음
📝 60-69%: 보통 - 부분적 관련성
📄 60% 미만: 낮음 - 낮은 관련성""")
        
        return container
    
    def mousePressEvent(self, event):
        self.on_card_clicked()
    
    def on_card_clicked(self):
        """카드 클릭 시 PDF 파일 열기"""
        self.card_clicked.emit({
            'file_path': self.doc_info.get('file_path'),
            'page_num': self.doc_info.get('page_num'),
            'content': self.content
        })

class PDFLoadingThread(QThread):
    """PDF 로딩 스레드"""
    progress_updated = pyqtSignal(str, int, int)  # 메시지, 현재, 전체
    file_progress = pyqtSignal(str, int, int)  # 파일명, 현재 페이지, 전체 페이지
    loading_completed = pyqtSignal()
    loading_failed = pyqtSignal(str)
    
    def __init__(self, index: MemoryEfficientDocumentIndex, file_paths: List[str]):
        super().__init__()
        self.index = index
        self.file_paths = file_paths
    
    def extract_text_from_pdf(self, pdf_path: str) -> List[Tuple[str, int]]:
        """PDF에서 페이지별 텍스트 추출"""
        try:
            pages_text = []
            filename = Path(pdf_path).name
            
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                total_pages = len(pdf_reader.pages)
                
                for page_num, page in enumerate(pdf_reader.pages, 1):
                    try:
                        # 파일별 진행률 시그널 방출
                        self.file_progress.emit(filename, page_num, total_pages)
                        
                        text = page.extract_text()
                        if text.strip():
                            pages_text.append((text.strip(), page_num))
                    except Exception:
                        continue
            
            return pages_text
        except Exception as e:
            raise Exception(f"PDF 읽기 실패: {str(e)}")
    
    def run(self):
        try:
            total_files = len(self.file_paths)
            
            for i, file_path in enumerate(self.file_paths, 1):
                filename = Path(file_path).name
                self.progress_updated.emit(f"분석 중: {filename}", i, total_files)
                
                if file_path.lower().endswith('.pdf'):
                    pages_text = self.extract_text_from_pdf(file_path)
                    
                    for page_text, page_num in pages_text:
                        doc_id = f"{filename}_page_{page_num}"
                        metadata = {
                            'file_path': file_path,
                            'filename': filename,
                            'page_num': page_num
                        }
                        
                        self.index.add_document(doc_id, page_text, metadata)
                
            self.loading_completed.emit()
            
        except Exception as e:
            self.loading_failed.emit(f"로딩 실패: {str(e)}")

class SearchThread(QThread):
    """검색 스레드"""
    search_completed = pyqtSignal(list, float)
    search_failed = pyqtSignal(str)
    
    def __init__(self, index: MemoryEfficientDocumentIndex, query: str, top_k: int = 10):
        super().__init__()
        self.index = index
        self.query = query
        self.top_k = top_k
    
    def run(self):
        try:
            start_time = time.time()
            results = self.index.search(self.query, top_k=self.top_k, min_similarity=0.15)
            search_time = time.time() - start_time
            
            formatted_results = []
            for result in results:
                if isinstance(result, dict) and 'content' in result:
                    metadata = result.get('metadata', {})
                    doc_info = {
                        'file_path': metadata.get('file_path', ''),
                        'page_num': metadata.get('page_num', 0)
                    }
                    # similarity_score 키를 사용 (memory_optimized_fix.py에서 사용하는 키)
                    similarity = result.get('similarity_score', result.get('similarity', 0))
                    formatted_results.append((result['content'], similarity, doc_info))
            
            self.search_completed.emit(formatted_results, search_time)
            
        except Exception as e:
            self.search_failed.emit(f"검색 오류: {str(e)}")

class AdvancedPDFSearchApp(QMainWindow):
    """고급 PDF 검색 앱"""
    
    def __init__(self):
        super().__init__()
        self.index = None
        self.pdf_loader_thread = None
        self.search_thread = None
        
        self.init_ai_model()
        self.init_ui()
        self.apply_theme()
    
    def init_ai_model(self):
        """AI 모델 초기화"""
        try:
            print("🚀 AI 시스템 초기화 중...")
            self.index = MemoryEfficientDocumentIndex()
            print("✅ AI 시스템 준비 완료!")
        except Exception as e:
            print(f"❌ AI 시스템 초기화 실패: {e}")
            sys.exit(1)
    
    def init_ui(self):
        """UI 초기화"""
        self.setWindowTitle("📚 PDF Search v1.0 - AI 기반 PDF 검색 도구")
        self.setGeometry(100, 100, 1400, 800)
        
        # 메인 위젯
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        
        # 2분할 레이아웃
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 왼쪽 컨트롤 패널
        control_panel = self.create_control_panel()
        
        # 오른쪽 결과 패널
        result_panel = self.create_result_panel()
        
        # 스플리터로 크기 조정 가능하게
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(control_panel)
        splitter.addWidget(result_panel)
        splitter.setSizes([400, 1000])
        splitter.setStyleSheet(f"""
            QSplitter::handle {{
                background-color: {ModernTheme.BORDER};
                width: 1px;
            }}
        """)
        
        main_layout.addWidget(splitter)
    
    def create_control_panel(self) -> QWidget:
        """왼쪽 컨트롤 패널"""
        panel = QWidget()
        panel.setStyleSheet(f"""
            QWidget {{
                background-color: {ModernTheme.PANEL_BG};
                border-right: 1px solid {ModernTheme.BORDER};
            }}
        """)
        
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        
        # 제목
        title = QLabel("📚 PDF 검색 시스템")
        title.setStyleSheet(f"""
            color: {ModernTheme.TEXT_PRIMARY};
            font-size: 20px;
            font-weight: bold;
            margin-bottom: 10px;
        """)
        layout.addWidget(title)
        
        # 1. 드래그 앤 드롭 영역
        self.drop_area = DragDropArea()
        self.drop_area.files_dropped.connect(self.add_files)
        layout.addWidget(self.drop_area)
        
        # 2. 파일 선택 버튼들
        button_layout = QHBoxLayout()
        
        self.add_files_btn = QPushButton("📄 파일 선택")
        self.add_files_btn.clicked.connect(self.add_pdf_files)
        
        self.add_folder_btn = QPushButton("📁 폴더 선택")
        self.add_folder_btn.clicked.connect(self.add_pdf_folder)
        
        for btn in [self.add_files_btn, self.add_folder_btn]:
            btn.setStyleSheet(ModernTheme.button_style())
        
        button_layout.addWidget(self.add_files_btn)
        button_layout.addWidget(self.add_folder_btn)
        layout.addLayout(button_layout)
        
        # 3. 파일 목록
        self.file_list = FileListWidget()
        layout.addWidget(self.file_list)
        
        # 4. 진행률 표시 (실시간 로딩바로 개선)
        progress_frame = QFrame()
        progress_frame.setStyleSheet(ModernTheme.frame_style())
        
        progress_layout = QVBoxLayout(progress_frame)
        progress_layout.setContentsMargins(12, 12, 12, 12)
        progress_layout.setSpacing(8)
        
        self.progress_label = QLabel("파일을 추가하여 시작하세요")
        self.progress_label.setStyleSheet(f"""
            color: {ModernTheme.TEXT_SECONDARY};
            font-size: 12px;
            font-weight: bold;
        """)
        
        # 전체 파일 진행률
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet(ModernTheme.progress_bar_style())
        
        # 현재 파일의 페이지 진행률
        self.file_progress_label = QLabel("")
        self.file_progress_label.setVisible(False)
        self.file_progress_label.setStyleSheet(f"""
            color: {ModernTheme.TEXT_SECONDARY};
            font-size: 11px;
            font-style: italic;
        """)
        
        self.file_progress_bar = QProgressBar()
        self.file_progress_bar.setVisible(False)
        self.file_progress_bar.setStyleSheet(ModernTheme.progress_bar_style(ModernTheme.SUCCESS).replace("height: 10px", "height: 6px"))
        
        progress_layout.addWidget(self.progress_label)
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.file_progress_label)
        progress_layout.addWidget(self.file_progress_bar)
        
        layout.addWidget(progress_frame)
        
        # 5. 검색 섹션
        search_frame = QFrame()
        search_frame.setStyleSheet(ModernTheme.frame_style())
        
        search_layout = QVBoxLayout(search_frame)
        search_layout.setContentsMargins(16, 16, 16, 16)
        
        search_title = QLabel("🔍 스마트 검색")
        search_title.setStyleSheet(f"""
            color: {ModernTheme.TEXT_PRIMARY};
            font-size: 16px;
            font-weight: bold;
            margin-bottom: 12px;
        """)
        search_layout.addWidget(search_title)
        
        # 검색 영역을 여러 줄 텍스트로 변경
        search_container = QFrame()
        search_container.setStyleSheet(f"""
            QFrame {{
                background-color: {ModernTheme.BACKGROUND};
                border: 1px solid {ModernTheme.BORDER};
                border-radius: 8px;
                padding: 4px;
            }}
        """)
        
        search_inner_layout = QVBoxLayout(search_container)
        search_inner_layout.setContentsMargins(0, 0, 0, 0)
        search_inner_layout.setSpacing(0)
        
        # 여러 줄 검색창
        self.search_input = QTextEdit()
        self.search_input.setPlaceholderText("이곳에 원본 또는 변형된 지문을 붙여넣어 검색하세요...\n\n예시:\n• 미적분학의 기본 정리\n• 파이썬에서 리스트 컴프리헨션 사용법\n• 양자역학의 불확정성 원리")
        self.search_input.setMaximumHeight(120)  # 5-7줄 높이
        self.search_input.setMinimumHeight(80)
        self.search_input.setStyleSheet(f"""
            QTextEdit {{
                background-color: {ModernTheme.BACKGROUND};
                color: {ModernTheme.TEXT_PRIMARY};
                border: none;
                padding: 12px 16px;
                font-size: 14px;
                line-height: 1.5;
                font-family: 'Segoe UI', Arial, sans-serif;
            }}
            QTextEdit:focus {{
                background-color: {ModernTheme.PANEL_BG};
            }}
        """)
        
        # 검색창 상단 툴바
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setContentsMargins(8, 4, 8, 4)
        
        # 입력 상태 표시
        self.char_count_label = QLabel("0 글자")
        self.char_count_label.setStyleSheet(f"""
            color: {ModernTheme.TEXT_SECONDARY};
            font-size: 10px;
        """)
        
        # 내용 지우기 버튼
        clear_btn = QPushButton("✕")
        clear_btn.setFixedSize(20, 20)
        clear_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ModernTheme.TEXT_SECONDARY};
                color: white;
                border: none;
                border-radius: 10px;
                font-size: 12px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {ModernTheme.ERROR};
            }}
        """)
        clear_btn.clicked.connect(self.clear_search_input)
        clear_btn.setToolTip("검색창 내용 모두 지우기")
        
        toolbar_layout.addWidget(self.char_count_label)
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(clear_btn)
        
        search_inner_layout.addLayout(toolbar_layout)
        search_inner_layout.addWidget(self.search_input)
        
        # 검색창 내용 변경 시 글자 수 업데이트
        self.search_input.textChanged.connect(self.update_char_count)
        
        # 검색 버튼
        self.search_btn = QPushButton("🚀 검색 시작")
        self.search_btn.clicked.connect(self.perform_search)
        self.search_btn.setEnabled(False)  # 처음에는 비활성화
        self.search_btn.setStyleSheet(ModernTheme.button_style(ModernTheme.SUCCESS, "#138d75"))
        
        search_layout.addWidget(search_container)
        search_layout.addWidget(self.search_btn)
        
        layout.addWidget(search_frame)
        layout.addStretch()
        
        return panel
    
    def create_result_panel(self) -> QWidget:
        """오른쪽 결과 패널"""
        panel = QWidget()
        panel.setStyleSheet(f"""
            QWidget {{
                background-color: {ModernTheme.BACKGROUND};
            }}
        """)
        
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 제목
        self.result_title = QLabel("📋 검색 결과")
        self.result_title.setStyleSheet(f"""
            color: {ModernTheme.TEXT_PRIMARY};
            font-size: 18px;
            font-weight: bold;
            margin-bottom: 16px;
        """)
        layout.addWidget(self.result_title)
        
        # 결과 스크롤 영역
        self.result_scroll = QScrollArea()
        self.result_scroll.setWidgetResizable(True)
        self.result_scroll.setStyleSheet(f"""
            QScrollArea {{
                background-color: transparent;
                border: none;
            }}
            QScrollBar:vertical {{
                background-color: {ModernTheme.PANEL_BG};
                width: 12px;
                border-radius: 6px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {ModernTheme.BORDER};
                border-radius: 6px;
                min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: {ModernTheme.PRIMARY};
            }}
        """)
        
        # 초기 상태 위젯
        self.empty_state = QWidget()
        empty_layout = QVBoxLayout(self.empty_state)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        empty_icon = QLabel("🔍")
        empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_icon.setStyleSheet("font-size: 64px; margin: 20px;")
        
        empty_text = QLabel("왼쪽에서 PDF 파일을 추가하고\n검색을 시작해보세요!")
        empty_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_text.setStyleSheet(f"""
            color: {ModernTheme.TEXT_SECONDARY};
            font-size: 16px;
            line-height: 1.5;
        """)
        
        empty_layout.addWidget(empty_icon)
        empty_layout.addWidget(empty_text)
        
        self.result_scroll.setWidget(self.empty_state)
        layout.addWidget(self.result_scroll)
        
        return panel
    
    def apply_theme(self):
        """테마 적용"""
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {ModernTheme.BACKGROUND};
                color: {ModernTheme.TEXT_PRIMARY};
            }}
        """)
    
    def clear_search_input(self):
        """검색창 내용 지우기"""
        self.search_input.clear()
        self.search_input.setFocus()
    
    def update_char_count(self):
        """글자 수 업데이트"""
        text = self.search_input.toPlainText()
        char_count = len(text)
        
        if char_count == 0:
            self.char_count_label.setText("입력 대기")
            self.char_count_label.setStyleSheet(f"color: {ModernTheme.TEXT_SECONDARY}; font-size: 10px;")
        elif char_count < 10:
            self.char_count_label.setText(f"{char_count} 글자")
            self.char_count_label.setStyleSheet(f"color: {ModernTheme.WARNING}; font-size: 10px;")
        else:
            self.char_count_label.setText(f"{char_count} 글자")
            self.char_count_label.setStyleSheet(f"color: {ModernTheme.SUCCESS}; font-size: 10px;")
    
    def add_files(self, file_paths: List[str]):
        """파일 추가"""
        self.file_list.add_files(file_paths)
        self._start_processing()
    
    def add_pdf_files(self):
        """PDF 파일 선택"""
        files, _ = QFileDialog.getOpenFileNames(
            self, "PDF 파일 선택", "", "PDF files (*.pdf)"
        )
        if files:
            self.add_files(files)
    
    def add_pdf_folder(self):
        """폴더 선택"""
        folder = QFileDialog.getExistingDirectory(self, "폴더 선택")
        if folder:
            pdf_files = list(Path(folder).glob("**/*.pdf"))
            if pdf_files:
                self.add_files([str(f) for f in pdf_files])
            else:
                self.progress_label.setText("❌ 선택한 폴더에 PDF 파일이 없습니다")
    
    def _start_processing(self):
        """PDF 처리 시작"""
        if not self.file_list.files:
            return
        
        # 기존 스레드가 있다면 정리
        if self.pdf_loader_thread and self.pdf_loader_thread.isRunning():
            self.pdf_loader_thread.quit()
            self.pdf_loader_thread.wait()
        
        # 로딩 상태로 전환
        self.set_loading_state(True)
        self.add_files_btn.setEnabled(False)
        self.add_folder_btn.setEnabled(False)
        
        self.pdf_loader_thread = PDFLoadingThread(self.index, self.file_list.files)
        self.pdf_loader_thread.progress_updated.connect(self._update_progress)
        self.pdf_loader_thread.file_progress.connect(self.update_file_progress)
        self.pdf_loader_thread.loading_completed.connect(self._on_loading_completed)
        self.pdf_loader_thread.loading_failed.connect(self._on_loading_failed)
        self.pdf_loader_thread.start()
    
    def _update_progress(self, message: str, current: int, total: int):
        """진행률 업데이트"""
        self.progress_label.setText(message)
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
    
    def _on_loading_completed(self):
        """로딩 완료"""
        # 로딩 상태 해제
        self.set_loading_state(False)
        self.add_files_btn.setEnabled(True)
        self.add_folder_btn.setEnabled(True)
        
        doc_count = len(self.index.documents)
        self.progress_label.setText(f"✅ 분석 완료! 총 {doc_count}개 페이지 준비됨")
    
    def _on_loading_failed(self, error_msg: str):
        """로딩 실패"""
        # 로딩 상태 해제
        self.set_loading_state(False)
        self.add_files_btn.setEnabled(True)
        self.add_folder_btn.setEnabled(True)
        
        self.progress_label.setText(f"❌ {error_msg}")
    
    def perform_search(self):
        """검색 수행"""
        query = self.search_input.toPlainText().strip()
        
        if not query:
            self.progress_label.setText("⚠️ 검색어를 입력해주세요")
            return
        
        if len(query) < 3:
            self.progress_label.setText("⚠️ 검색어는 3글자 이상 입력해주세요")
            return
        
        if not self.index or len(self.index.documents) == 0:
            self.progress_label.setText("⚠️ 먼저 PDF 파일을 추가해주세요")
            return
        
        # 기존 검색 스레드가 있다면 정리
        if self.search_thread and self.search_thread.isRunning():
            self.search_thread.quit()
            self.search_thread.wait()
        
        # 검색 상태로 전환
        self.set_loading_state(True)
        self.search_btn.setText("🔄 검색 중...")
        
        self.search_thread = SearchThread(self.index, query)
        self.search_thread.search_completed.connect(self._on_search_completed)
        self.search_thread.search_failed.connect(self._on_search_failed)
        self.search_thread.start()
    
    def _on_search_completed(self, results: List[Tuple], search_time: float):
        """검색 완료"""
        # 검색 상태 해제
        self.set_loading_state(False)
        
        if not results:
            self.result_title.setText(f"📋 검색 결과 (0개, {search_time:.2f}초)")
            self.result_scroll.setWidget(self.empty_state)
            self.progress_label.setText("🔍 검색 완료 - 결과 없음")
            return
        
        # 결과 카드들 생성
        result_widget = QWidget()
        result_layout = QVBoxLayout(result_widget)
        result_layout.setContentsMargins(0, 0, 0, 0)
        result_layout.setSpacing(0)
        
        for content, similarity, doc_info in results:
            card = ResultCard(content, similarity, doc_info)
            card.card_clicked.connect(self._open_pdf)
            result_layout.addWidget(card)
        
        result_layout.addStretch()
        
        self.result_scroll.setWidget(result_widget)
        self.result_title.setText(f"📋 검색 결과 ({len(results)}개, {search_time:.2f}초)")
        self.progress_label.setText(f"✅ 검색 완료 - {len(results)}개 결과")
    
    def _on_search_failed(self, error_msg: str):
        """검색 실패"""
        # 검색 상태 해제
        self.set_loading_state(False)
        self.progress_label.setText(f"❌ {error_msg}")
    
    def update_file_progress(self, current_file, current_page, total_pages):
        """파일별 진행률 업데이트"""
        if total_pages > 0:
            progress = (current_page / total_pages) * 100
            self.progress_bar.setValue(int(progress))
            
            # 파일명이 길면 줄임 처리
            display_name = current_file[:22] + "..." if len(current_file) > 25 else current_file
            self.progress_label.setText(f"📄 {display_name} 처리 중... ({current_page}/{total_pages} 페이지)")
        
    def set_loading_state(self, is_loading):
        """로딩 상태에 따른 UI 상태 변경"""
        self.search_input.setEnabled(not is_loading)
        self.search_btn.setEnabled(not is_loading and bool(self.index.documents))
        
        if is_loading:
            self.search_btn.setText("⏳ 처리 중...")
            self.progress_bar.show()
        else:
            self.search_btn.setText("🚀 검색 시작")
            self.progress_bar.hide()
            if hasattr(self, 'index') and self.index.documents:
                self.progress_label.setText(f"✅ {len(self.index.documents)}개 문서 로드 완료")
            else:
                self.progress_label.setText("📁 PDF 파일을 드래그하여 추가하세요")
    
    def closeEvent(self, event):
        """앱 종료 시 스레드 정리"""
        if self.pdf_loader_thread and self.pdf_loader_thread.isRunning():
            self.pdf_loader_thread.quit()
            self.pdf_loader_thread.wait()
        
        if self.search_thread and self.search_thread.isRunning():
            self.search_thread.quit()
            self.search_thread.wait()
        
        event.accept()

    def _open_pdf(self, data: dict):
        """PDF 파일 열기"""
        file_path = data['file_path']
        page_num = data['page_num']
        
        if os.path.exists(file_path):
            # Windows에서 PDF 파일 열기
            os.startfile(file_path)
            self.progress_label.setText(f"📖 PDF 열림: {Path(file_path).name} (p.{page_num})")
        else:
            self.progress_label.setText("❌ 파일을 찾을 수 없습니다")

def main():
    """메인 함수"""
    app = QApplication(sys.argv)
    
    app.setApplicationName("PDF Search v1.0")
    app.setApplicationVersion("1.0")
    
    window = AdvancedPDFSearchApp()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()