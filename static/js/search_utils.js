/**
 * Универсальные утилиты для поиска и фильтрации
 * Поддерживает поиск с любого места, любой регистр, нормализацию
 */

/**
 * Нормализует текст для поиска
 * - Убирает лишние пробелы
 * - Приводит к нижнему регистру
 * - Убирает специальные символы для более гибкого поиска
 */
function normalizeSearchText(text) {
    if (!text || typeof text !== 'string') return '';
    
    // Убираем лишние пробелы и приводим к нижнему регистру
    let normalized = text.trim().toLowerCase();
    
    // Убираем множественные пробелы
    normalized = normalized.replace(/\s+/g, ' ');
    
    return normalized;
}

/**
 * Проверяет, соответствует ли текст поисковому запросу
 * @param {string} text - Текст для проверки
 * @param {string} searchTerm - Поисковый запрос
 * @returns {boolean} - true если текст соответствует запросу
 */
function matchesSearch(text, searchTerm) {
    if (!searchTerm) return true;
    if (!text) return false;
    
    const normalizedText = normalizeSearchText(String(text));
    const normalizedSearch = normalizeSearchText(String(searchTerm));
    
    // Ищем вхождение поискового запроса в тексте
    return normalizedText.includes(normalizedSearch);
}

/**
 * Фильтрует массив объектов по поисковому запросу
 * @param {Array} items - Массив объектов для фильтрации
 * @param {string} searchTerm - Поисковый запрос
 * @param {Array|Function} searchFields - Поля для поиска (массив строк или функция)
 * @returns {Array} - Отфильтрованный массив
 */
function filterBySearch(items, searchTerm, searchFields) {
    if (!searchTerm || !searchTerm.trim()) {
        return items;
    }
    
    const normalizedSearch = normalizeSearchText(searchTerm);
    
    return items.filter(item => {
        // Если searchFields - функция, используем её
        if (typeof searchFields === 'function') {
            const searchableText = searchFields(item);
            return matchesSearch(searchableText, normalizedSearch);
        }
        
        // Если searchFields - массив строк, ищем в указанных полях
        if (Array.isArray(searchFields)) {
            return searchFields.some(field => {
                const value = getNestedValue(item, field);
                return matchesSearch(value, normalizedSearch);
            });
        }
        
        // По умолчанию ищем во всех строковых полях объекта
        return Object.values(item).some(value => {
            if (typeof value === 'string' || typeof value === 'number') {
                return matchesSearch(String(value), normalizedSearch);
            }
            return false;
        });
    });
}

/**
 * Получает вложенное значение объекта по пути (например, 'user.name')
 */
function getNestedValue(obj, path) {
    if (!obj || !path) return '';
    
    const keys = path.split('.');
    let value = obj;
    
    for (const key of keys) {
        if (value && typeof value === 'object' && key in value) {
            value = value[key];
        } else {
            return '';
        }
    }
    
    return value || '';
}

/**
 * Создает обработчик поиска с debounce
 * @param {Function} callback - Функция, которая будет вызвана при поиске
 * @param {number} delay - Задержка в миллисекундах (по умолчанию 300)
 * @returns {Function} - Обработчик события
 */
function createSearchHandler(callback, delay = 300) {
    let timeout;
    
    return function(event) {
        clearTimeout(timeout);
        timeout = setTimeout(() => {
            callback(event);
        }, delay);
    };
}

/**
 * Создает обработчик поиска с немедленным выполнением при нажатии Enter
 * @param {Function} callback - Функция, которая будет вызвана при поиске
 * @param {number} delay - Задержка для обычного поиска (по умолчанию 300)
 * @returns {Object} - Объект с обработчиками input и keypress
 */
function createAdvancedSearchHandler(callback, delay = 300) {
    const inputHandler = createSearchHandler(callback, delay);
    
    const keypressHandler = function(event) {
        if (event.key === 'Enter') {
            event.preventDefault();
            clearTimeout();
            callback(event);
        }
    };
    
    const keydownHandler = function(event) {
        if (event.key === 'Escape') {
            event.target.value = '';
            callback(event);
        }
    };
    
    return {
        input: inputHandler,
        keypress: keypressHandler,
        keydown: keydownHandler
    };
}
