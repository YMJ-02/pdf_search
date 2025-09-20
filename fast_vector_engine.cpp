#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/numpy.h>
#include <vector>
#include <cmath>
#include <algorithm>
#include <unordered_map>
#include <queue>
#include <memory>
#include <immintrin.h>
#include <omp.h>

namespace py = pybind11;

struct SearchResult {
    int doc_id;
    float similarity;
    
    SearchResult() : doc_id(0), similarity(0.0f) {}
    SearchResult(int id, float sim) : doc_id(id), similarity(sim) {}
    
    bool operator<(const SearchResult& other) const {
        return similarity < other.similarity;
    }
    
    bool operator>(const SearchResult& other) const {
        return similarity > other.similarity;
    }
};

class FastVectorEngine {
private:
    size_t vector_dimension_;
    std::vector<std::vector<float>> document_vectors_;
    std::vector<int> document_ids_;
    std::unordered_map<int, size_t> id_to_index_;
    
public:
    FastVectorEngine(size_t dim = 384) : vector_dimension_(dim) {}
    
    float cosine_similarity_simd(const std::vector<float>& vec1, const std::vector<float>& vec2) {
        if (vec1.size() != vec2.size() || vec1.size() != vector_dimension_) {
            throw std::invalid_argument("Vector dimensions must match");
        }
        
        float dot_product = 0.0f;
        float norm1 = 0.0f;
        float norm2 = 0.0f;
        
        size_t simd_size = (vec1.size() / 8) * 8;
        
        __m256 sum_dot = _mm256_setzero_ps();
        __m256 sum_norm1 = _mm256_setzero_ps();
        __m256 sum_norm2 = _mm256_setzero_ps();
        
        for (size_t i = 0; i < simd_size; i += 8) {
            __m256 v1 = _mm256_loadu_ps(&vec1[i]);
            __m256 v2 = _mm256_loadu_ps(&vec2[i]);
            
            sum_dot = _mm256_fmadd_ps(v1, v2, sum_dot);
            sum_norm1 = _mm256_fmadd_ps(v1, v1, sum_norm1);
            sum_norm2 = _mm256_fmadd_ps(v2, v2, sum_norm2);
        }
        
        float dot_array[8], norm1_array[8], norm2_array[8];
        _mm256_storeu_ps(dot_array, sum_dot);
        _mm256_storeu_ps(norm1_array, sum_norm1);
        _mm256_storeu_ps(norm2_array, sum_norm2);
        
        for (int i = 0; i < 8; i++) {
            dot_product += dot_array[i];
            norm1 += norm1_array[i];
            norm2 += norm2_array[i];
        }
        
        for (size_t i = simd_size; i < vec1.size(); i++) {
            dot_product += vec1[i] * vec2[i];
            norm1 += vec1[i] * vec1[i];
            norm2 += vec2[i] * vec2[i];
        }
        
        float magnitude = std::sqrt(norm1) * std::sqrt(norm2);
        return magnitude > 1e-8f ? dot_product / magnitude : 0.0f;
    }
    
    void add_document(int doc_id, const std::vector<float>& embedding) {
        if (embedding.size() != vector_dimension_) {
            throw std::invalid_argument("Embedding dimension mismatch");
        }
        
        size_t index = document_vectors_.size();
        document_vectors_.push_back(embedding);
        document_ids_.push_back(doc_id);
        id_to_index_[doc_id] = index;
    }
    
    std::vector<SearchResult> search_parallel(const std::vector<float>& query_vector, 
                                              int top_k = 10, float min_similarity = 0.0f) {
        if (query_vector.size() != vector_dimension_) {
            throw std::invalid_argument("Query vector dimension mismatch");
        }
        
        std::vector<SearchResult> results;
        results.reserve(document_vectors_.size());
        
        #pragma omp parallel for
        for (int i = 0; i < (int)document_vectors_.size(); i++) {
            float similarity = cosine_similarity_simd(query_vector, document_vectors_[i]);
            
            if (similarity >= min_similarity) {
                #pragma omp critical
                {
                    results.emplace_back(document_ids_[i], similarity);
                }
            }
        }
        
        std::partial_sort(results.begin(), 
                         results.begin() + std::min(top_k, (int)results.size()),
                         results.end(),
                         std::greater<SearchResult>());
        
        if (results.size() > (size_t)top_k) {
            results.resize(top_k);
        }
        
        return results;
    }
    
    std::vector<std::vector<SearchResult>> search_batch(
        const std::vector<std::vector<float>>& query_vectors,
        int top_k = 10, float min_similarity = 0.0f) {
        
        std::vector<std::vector<SearchResult>> batch_results(query_vectors.size());
        
        #pragma omp parallel for
        for (int q = 0; q < (int)query_vectors.size(); q++) {
            batch_results[q] = search_parallel(query_vectors[q], top_k, min_similarity);
        }
        
        return batch_results;
    }
    
    std::vector<int8_t> quantize_vector(const std::vector<float>& vector) {
        std::vector<int8_t> quantized(vector.size());
        
        float min_val = *std::min_element(vector.begin(), vector.end());
        float max_val = *std::max_element(vector.begin(), vector.end());
        float scale = 255.0f / (max_val - min_val);
        
        for (size_t i = 0; i < vector.size(); i++) {
            quantized[i] = static_cast<int8_t>((vector[i] - min_val) * scale - 128);
        }
        
        return quantized;
    }
    
    size_t get_document_count() const { return document_vectors_.size(); }
    size_t get_vector_dimension() const { return vector_dimension_; }
    
    size_t get_memory_usage() const {
        size_t base_size = sizeof(*this);
        size_t vectors_size = document_vectors_.size() * vector_dimension_ * sizeof(float);
        size_t ids_size = document_ids_.size() * sizeof(int);
        size_t map_size = id_to_index_.size() * (sizeof(int) + sizeof(size_t));
        return base_size + vectors_size + ids_size + map_size;
    }
};

PYBIND11_MODULE(fast_vector_engine, m) {
    m.doc() = "High-performance C++ vector search engine with SIMD and OpenMP optimization";
    
    py::class_<SearchResult>(m, "SearchResult")
        .def(py::init<int, float>())
        .def_readwrite("doc_id", &SearchResult::doc_id)
        .def_readwrite("similarity", &SearchResult::similarity);
    
    py::class_<FastVectorEngine>(m, "FastVectorEngine")
        .def(py::init<size_t>(), py::arg("dim") = 384)
        .def("add_document", &FastVectorEngine::add_document, py::arg("doc_id"), py::arg("embedding"))
        .def("search_parallel", &FastVectorEngine::search_parallel, py::arg("query_vector"), py::arg("top_k") = 10, py::arg("min_similarity") = 0.0f)
        .def("search_batch", &FastVectorEngine::search_batch, py::arg("query_vectors"), py::arg("top_k") = 10, py::arg("min_similarity") = 0.0f)
        .def("cosine_similarity_simd", &FastVectorEngine::cosine_similarity_simd, py::arg("vec1"), py::arg("vec2"))
        .def("quantize_vector", &FastVectorEngine::quantize_vector, py::arg("vector"))
        .def("get_document_count", &FastVectorEngine::get_document_count)
        .def("get_vector_dimension", &FastVectorEngine::get_vector_dimension)
        .def("get_memory_usage", &FastVectorEngine::get_memory_usage);
}