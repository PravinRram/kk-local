// Shared logic for persisting event creation state

const STORAGE_KEY = 'kk_create_event_data';

// Initialize storage if empty
function initStorage() {
    if (!localStorage.getItem(STORAGE_KEY)) {
        localStorage.setItem(STORAGE_KEY, JSON.stringify({
            method: 'manual',
            type: '',
            name: '',
            date: '',
            time: '',
            duration_days: '',
            duration_hours: '',
            duration_mins: '',
            location: '',
            description: '',
            visibility: '',
            imgMethod: '',
            imgData: '', // Base64 for preview
            imgName: '',
            features: []
        }));
    }
}

function getEventData() {
    initStorage();
    return JSON.parse(localStorage.getItem(STORAGE_KEY));
}

function updateEventData(updates) {
    const data = getEventData();
    const newData = { ...data, ...updates };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(newData));
}

// Helper to handle form inputs automatically
function saveInput(name, value) {
    updateEventData({ [name]: value });
}

function loadInput(name, elementId) {
    const data = getEventData();
    const el = document.getElementById(elementId);
    if (el && data[name]) {
        el.value = data[name];
    }
}
