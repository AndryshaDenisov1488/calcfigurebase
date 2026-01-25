// Основной JavaScript для системы управления турнирами по фигурному катанию

document.addEventListener('DOMContentLoaded', function() {
    // Инициализация компонентов
    initializeTooltips();
    initializeAlerts();
    initializeTables();
    initializeSearch();
});

// Инициализация тултипов Bootstrap
function initializeTooltips() {
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

// Автоматическое скрытие алертов
function initializeAlerts() {
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        if (alert.classList.contains('alert-success') || alert.classList.contains('alert-info')) {
            setTimeout(() => {
                const bsAlert = new bootstrap.Alert(alert);
                bsAlert.close();
            }, 5000);
        }
    });
}

// Инициализация таблиц
function initializeTables() {
    // Добавляем классы для стилизации таблиц
    const tables = document.querySelectorAll('.table');
    tables.forEach(table => {
        table.classList.add('table-hover');
    });
}

// Инициализация поиска
function initializeSearch() {
    // Исключаем страницу спортсменов - там свой поиск через API
    if (window.location.pathname === '/athletes') {
        return; // Не инициализируем поиск на странице спортсменов
    }
    
    const searchInputs = document.querySelectorAll('input[type="search"]');
    searchInputs.forEach(input => {
        // Проверяем, что это не поле поиска спортсменов
        if (input.id !== 'searchInput') {
            input.addEventListener('input', debounce(handleSearch, 300));
        }
    });
}

// Обработка поиска (только для статических таблиц)
function handleSearch(event) {
    const searchTerm = event.target.value.toLowerCase();
    const card = event.target.closest('.card');
    
    if (!card) {
        return; // Если нет родительского .card, выходим
    }
    
    const table = card.querySelector('table');
    
    if (table) {
        const rows = table.querySelectorAll('tbody tr');
        rows.forEach(row => {
            const text = row.textContent.toLowerCase();
            if (text.includes(searchTerm)) {
                row.style.display = '';
            } else {
                row.style.display = 'none';
            }
        });
    }
}

// Функция debounce для оптимизации поиска
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Показать статистику
function showStatistics() {
    // Создаем модальное окно со статистикой
    const modalHtml = `
        <div class="modal fade" id="statisticsModal" tabindex="-1">
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">
                            <i class="fas fa-chart-bar"></i> Статистика системы
                        </h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <div class="row">
                            <div class="col-md-6">
                                <canvas id="athletesChart" width="400" height="200"></canvas>
                            </div>
                            <div class="col-md-6">
                                <canvas id="eventsChart" width="400" height="200"></canvas>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    // Добавляем модальное окно в DOM
    document.body.insertAdjacentHTML('beforeend', modalHtml);
    
    // Показываем модальное окно
    const modal = new bootstrap.Modal(document.getElementById('statisticsModal'));
    modal.show();
    
    // Создаем графики
    createCharts();
    
    // Удаляем модальное окно после закрытия
    document.getElementById('statisticsModal').addEventListener('hidden.bs.modal', function() {
        this.remove();
    });
}

// Создание графиков
function createCharts() {
    // График спортсменов по клубам
    const athletesCtx = document.getElementById('athletesChart');
    if (athletesCtx) {
        new Chart(athletesCtx, {
            type: 'doughnut',
            data: {
                labels: ['Клуб 1', 'Клуб 2', 'Клуб 3', 'Другие'],
                datasets: [{
                    data: [30, 25, 20, 25],
                    backgroundColor: [
                        '#007bff',
                        '#28a745',
                        '#ffc107',
                        '#6c757d'
                    ]
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    title: {
                        display: true,
                        text: 'Распределение спортсменов по клубам'
                    }
                }
            }
        });
    }
    
    // График турниров по месяцам
    const eventsCtx = document.getElementById('eventsChart');
    if (eventsCtx) {
        new Chart(eventsCtx, {
            type: 'line',
            data: {
                labels: ['Янв', 'Фев', 'Мар', 'Апр', 'Май', 'Июн'],
                datasets: [{
                    label: 'Количество турниров',
                    data: [2, 3, 1, 4, 2, 3],
                    borderColor: '#007bff',
                    backgroundColor: 'rgba(0, 123, 255, 0.1)',
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    title: {
                        display: true,
                        text: 'Турниры по месяцам'
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true
                    }
                }
            }
        });
    }
}

// Экспорт данных
function exportData(format = 'csv') {
    const table = document.querySelector('.table');
    if (!table) return;
    
    let csv = '';
    const rows = table.querySelectorAll('tr');
    
    rows.forEach(row => {
        const cells = row.querySelectorAll('th, td');
        const rowData = Array.from(cells).map(cell => {
            return '"' + cell.textContent.replace(/"/g, '""') + '"';
        });
        csv += rowData.join(',') + '\n';
    });
    
    // Создаем и скачиваем файл
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'export.csv';
    a.click();
    window.URL.revokeObjectURL(url);
}

// Печать результатов
function printResults() {
    window.print();
}

// Поделиться результатами
function shareResults() {
    if (navigator.share) {
        navigator.share({
            title: document.title,
            text: 'Результаты турнира по фигурному катанию',
            url: window.location.href
        });
    } else {
        // Fallback - копируем ссылку в буфер обмена
        navigator.clipboard.writeText(window.location.href).then(() => {
            showToast('Ссылка скопирована в буфер обмена', 'success');
        }).catch(() => {
            showToast('Не удалось скопировать ссылку', 'error');
        });
    }
}

// Показать уведомление
function showToast(message, type = 'info') {
    const toastHtml = `
        <div class="toast align-items-center text-white bg-${type === 'error' ? 'danger' : type} border-0" role="alert">
            <div class="d-flex">
                <div class="toast-body">
                    <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'}"></i>
                    ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        </div>
    `;
    
    // Создаем контейнер для тостов, если его нет
    let toastContainer = document.querySelector('.toast-container');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.className = 'toast-container position-fixed top-0 end-0 p-3';
        document.body.appendChild(toastContainer);
    }
    
    // Добавляем тост
    toastContainer.insertAdjacentHTML('beforeend', toastHtml);
    
    // Показываем тост
    const toastElement = toastContainer.lastElementChild;
    const toast = new bootstrap.Toast(toastElement);
    toast.show();
    
    // Удаляем тост после скрытия
    toastElement.addEventListener('hidden.bs.toast', function() {
        this.remove();
    });
}

// Валидация форм
function validateForm(form) {
    const inputs = form.querySelectorAll('input[required], select[required], textarea[required]');
    let isValid = true;
    
    inputs.forEach(input => {
        if (!input.value.trim()) {
            input.classList.add('is-invalid');
            isValid = false;
        } else {
            input.classList.remove('is-invalid');
        }
    });
    
    return isValid;
}

// Форматирование чисел
function formatNumber(num) {
    return new Intl.NumberFormat('ru-RU').format(num);
}

// Форматирование даты
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('ru-RU');
}

// Анимация загрузки
function showLoading(element) {
    const originalContent = element.innerHTML;
    element.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Загрузка...';
    element.disabled = true;
    
    return function hideLoading() {
        element.innerHTML = originalContent;
        element.disabled = false;
    };
}

// Обработка ошибок AJAX
function handleAjaxError(xhr, status, error) {
    console.error('AJAX Error:', status, error);
    showToast('Произошла ошибка при загрузке данных', 'error');
}

// Утилиты для работы с URL
const urlUtils = {
    getParameter: function(name) {
        const urlParams = new URLSearchParams(window.location.search);
        return urlParams.get(name);
    },
    
    setParameter: function(name, value) {
        const url = new URL(window.location);
        url.searchParams.set(name, value);
        window.history.pushState({}, '', url);
    },
    
    removeParameter: function(name) {
        const url = new URL(window.location);
        url.searchParams.delete(name);
        window.history.pushState({}, '', url);
    }
};

// Экспорт функций для глобального использования
window.showStatistics = showStatistics;
window.exportData = exportData;
window.printResults = printResults;
window.shareResults = shareResults;
window.showToast = showToast;
window.validateForm = validateForm;
window.formatNumber = formatNumber;
window.formatDate = formatDate;
window.showLoading = showLoading;
window.urlUtils = urlUtils;
