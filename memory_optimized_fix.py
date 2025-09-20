#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
memory_optimized_fix.py - 메모리 사용량 최적화 및 누수 수정
"""

import numpy as np
from sentence_transformers import SentenceTransformer
import torch
import gc
import threading
import weakref
from typing import List, Union, Optional, Dict, Any
from dataclasses import dataclass

class UltraLightEmbedder:
    """메모리 사용량을 극도로 최적화한 임베딩 생성기"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        """
        초경량 임베딩 생성기 초기화
        - all-MiniLM-L6-v2: 가장 가벼운 모델 (23MB, 384차원)
        """
        if hasattr(self, '_initialized') and self._initialized:
            return
            
        print(f"🤖 로딩 중: {model_name} (경량 모델)")
        
        # PyTorch 메모리 최적화 설정
        torch.set_num_threads(1)  # 스레드 1개로 제한
        torch.set_num_interop_threads(1)
        
        # 모델 로드 시 메모리 최적화 옵션
        self.model = SentenceTransformer(
            model_name,
            device='cpu',
            trust_remote_code=False
        )
        
        # 모델을 evaluation 모드로 설정하고 gradient 비활성화
        self.model.eval()
        for param in self.model.parameters():
            param.requires_grad = False
        
        # 임베딩 차원 확인
        test_embedding = self._encode_single("test")
        self.embedding_dim = test_embedding.shape[0]
        
        print(f"✅ 경량 모델 로딩 완료! 차원: {self.embedding_dim}")
        
        self._initialized = True
        self._force_cleanup()
    
    def _encode_single(self, text: str) -> np.ndarray:
        """단일 텍스트 인코딩 (메모리 최적화)"""
        with torch.no_grad():
            embedding = self.model.encode(
                text,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
                batch_size=1  # 배치 크기 1로 제한
            )
        
        # 즉시 메모리 정리
        self._force_cleanup()
        
        return embedding.astype(np.float32)  # 메모리 절약
    
    def encode(self, texts: Union[str, List[str]], batch_size: int = 8) -> np.ndarray:
        """메모리 효율적 배치 인코딩"""
        if isinstance(texts, str):
            return self._encode_single(texts)
        
        # 작은 배치로 나누어 처리
        embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            
            with torch.no_grad():
                batch_embeddings = self.model.encode(
                    batch_texts,
                    convert_to_numpy=True,
                    normalize_embeddings=True,
                    show_progress_bar=False,
                    batch_size=len(batch_texts)
                )
            
            embeddings.append(batch_embeddings.astype(np.float32))
            
            # 배치마다 강제 메모리 정리
            self._force_cleanup()
        
        if embeddings:
            result = np.vstack(embeddings)
            # 최종 정리
            self._force_cleanup()
            return result
        
        return np.array([])
    
    def _force_cleanup(self):
        """강제 메모리 정리"""
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        gc.collect()  # 강제 가비지 컬렉션
    
    def __del__(self):
        """소멸자에서 강제 메모리 해제"""
        if hasattr(self, 'model'):
            del self.model
        self._force_cleanup()

class MemoryEfficientDocumentIndex:
    """메모리 효율성에 특화된 문서 인덱스"""
    
    def __init__(self, max_documents: int = 1000):
        self.max_documents = max_documents
        self.documents: List[Dict[str, Any]] = []  # 메타데이터만 저장
        self.embeddings: Optional[np.ndarray] = None
        
        # 싱글톤 임베더 사용
        self.embedder = UltraLightEmbedder()
        
        print(f"📚 메모리 효율적 인덱스 생성 (최대 {max_documents:,}개)")
    
    def add_document(self, doc_id: str, content: str, metadata: Optional[Dict] = None) -> bool:
        """메모리 효율적 문서 추가"""
        if len(self.documents) >= self.max_documents:
            return False
        
        # 중복 ID 체크
        if any(doc['id'] == doc_id for doc in self.documents):
            return False
        
        # 문서 메타데이터 저장 (내용은 임베딩으로만 저장)
        doc_info = {
            'id': doc_id,
            'content': content,  # 검색 결과에서 필요하므로 저장
            'metadata': metadata or {}
        }
        self.documents.append(doc_info)
        
        # 임베딩 생성 및 추가
        new_embedding = self.embedder.encode(content)
        
        if self.embeddings is None:
            self.embeddings = new_embedding.reshape(1, -1)
        else:
            self.embeddings = np.vstack([self.embeddings, new_embedding.reshape(1, -1)])
        
        # 주기적 메모리 정리
        if len(self.documents) % 50 == 0:  # 더 자주 정리
            gc.collect()
        
        return True
    
    def search(self, query: str, top_k: int = 5, min_similarity: float = 0.3) -> List[Dict]:
        """고성능 벡터 검색"""
        if not self.documents or self.embeddings is None:
            return []
        
        # 쿼리 임베딩
        query_embedding = self.embedder.encode(query)
        
        # 벡터화된 유사도 계산
        similarities = np.dot(self.embeddings, query_embedding)
        
        # 임계값 필터링
        valid_indices = np.where(similarities >= min_similarity)[0]
        
        if len(valid_indices) == 0:
            return []
        
        # 상위 k개 선택
        valid_similarities = similarities[valid_indices]
        top_indices = valid_indices[np.argsort(valid_similarities)[::-1][:top_k]]
        
        # 결과 구성
        results = []
        for idx in top_indices:
            doc = self.documents[idx]
            results.append({
                'id': doc['id'],
                'content': doc['content'],
                'similarity_score': float(similarities[idx]),
                'metadata': doc['metadata']
            })
        
        return results
    
    def get_memory_usage(self) -> Dict[str, float]:
        """현재 메모리 사용량"""
        import psutil
        process = psutil.Process()
        memory_mb = process.memory_info().rss / 1024 / 1024
        
        embedding_size_mb = 0
        if self.embeddings is not None:
            embedding_size_mb = self.embeddings.nbytes / 1024 / 1024
        
        return {
            'total_memory_mb': memory_mb,
            'embedding_cache_mb': embedding_size_mb,
            'document_count': len(self.documents)
        }
    
    def clear_all(self):
        """모든 데이터 정리"""
        self.documents.clear()
        self.embeddings = None
        gc.collect()

def test_memory_optimized_system():
    """메모리 최적화된 시스템 테스트"""
    import psutil
    import time
    
    print("🧪 메모리 최적화 시스템 테스트")
    print("=" * 40)
    
    process = psutil.Process()
    initial_memory = process.memory_info().rss / 1024 / 1024
    print(f"초기 메모리: {initial_memory:.1f} MB")
    
    # 인덱스 생성
    index = MemoryEfficientDocumentIndex(max_documents=100)
    after_init = process.memory_info().rss / 1024 / 1024
    print(f"인덱스 생성 후: {after_init:.1f} MB (+{after_init - initial_memory:.1f} MB)")
    
    # 테스트 문서 추가
    test_docs = [
        ("doc1", "인공지능과 머신러닝 기술 개발"),
        ("doc2", "웹 애플리케이션 프론트엔드 구축"),
        ("doc3", "데이터베이스 설계 및 최적화"),
        ("doc4", "클라우드 인프라 구축 가이드"),
        ("doc5", "모바일 앱 개발 프레임워크"),
    ]
    
    print(f"\n📚 {len(test_docs)}개 문서 추가...")
    
    for doc_id, content in test_docs:
        success = index.add_document(doc_id, content)
        if success:
            current_memory = process.memory_info().rss / 1024 / 1024
            print(f"  {doc_id}: {current_memory:.1f} MB")
    
    final_memory = process.memory_info().rss / 1024 / 1024
    print(f"\n문서 추가 완료: {final_memory:.1f} MB (+{final_memory - initial_memory:.1f} MB)")
    
    # 검색 테스트
    queries = ["인공지능", "웹개발", "데이터베이스"]
    
    print(f"\n🔍 검색 테스트:")
    for query in queries:
        start_time = time.time()
        results = index.search(query, top_k=3)
        search_time = time.time() - start_time
        
        print(f"  '{query}': {len(results)}개 결과, {search_time:.4f}초")
        for result in results:
            print(f"    - {result['id']}: {result['similarity_score']:.3f}")
    
    # 메모리 사용량 정보
    memory_info = index.get_memory_usage()
    print(f"\n📊 메모리 사용량:")
    for key, value in memory_info.items():
        if 'mb' in key:
            print(f"  {key}: {value:.2f} MB")
        else:
            print(f"  {key}: {value}")
    
    return final_memory - initial_memory

if __name__ == "__main__":
    memory_increase = test_memory_optimized_system()
    
    print(f"\n🎯 최종 결과:")
    if memory_increase < 100:  # 100MB 이하
        print(f"✅ 메모리 사용량 최적화 성공: +{memory_increase:.1f} MB")
    else:
        print(f"⚠️  메모리 사용량 개선 필요: +{memory_increase:.1f} MB")