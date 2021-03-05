function getDB() {
    return new Promise(((resolve, reject) => {
        let req = indexedDB.open("covid", 1);
        req.onupgradeneeded = () => {
            let db = req.result;
            if (!db.objectStoreNames.contains("cities")) {
                db.createObjectStore("cities", {keyPath: "id"});
            }
            if (!db.objectStoreNames.contains("subscription")) {
                db.createObjectStore("subscription", {keyPath: "id"});
            }
        }
        req.onsuccess = () => {
            resolve(req.result);
        }
        req.onerror = () => {
            reject(req.error);
        }
    }));

}

function wrapReq(req) {
    return new Promise(((resolve, reject) => {
        req.onsuccess = () => {
            resolve(req.result);
        }
        req.onerror = () => {
            reject(req.error);
        }
    }));
}

function updateCities(cities) {
    return getDB().then((db) => {
        let transaction = db.transaction("cities", "readwrite");
        let cityDb = transaction.objectStore("cities");
        return wrapReq(cityDb.clear()).then(() => {
            let p = []
            for (let city of cities) {
                p.push(wrapReq(cityDb.put(city)));
            }
            return Promise.all(p);
        })
    });
}

function getCities() {
    return getDB().then((db) => {
        let transaction = db.transaction("cities", "readonly");
        let cityDb = transaction.objectStore("cities");
        return wrapReq(cityDb.getAll());
    });
}

function updateSubscription(type, unsubscribe) {
    return getDB().then((db) => {
        let transaction = db.transaction("subscription", "readwrite");
        let subDb = transaction.objectStore("subscription");
        let sub = {
            id: 1,
            spotUnsubscribe: null,
            spotSubscription: false,
            groupUnsubscribe: null,
            groupSubscription: false
        }
        if (type === "spot" || type === "both") {
            sub.spotSubscription = true;
            sub.spotUnsubscribe = unsubscribe;
        }
        if (type === "group" || type === "both") {
            sub.groupSubscription = true;
            sub.groupUnsubscribe = unsubscribe;
        }
        return wrapReq(subDb.put(sub));
    });
}

function setSubscription(sub) {
    return getDB().then((db) => {
        let transaction = db.transaction("subscription", "readwrite");
        let subDb = transaction.objectStore("subscription");
        return wrapReq(subDb.put(sub));
    });
}

function getSubscription() {
    return getDB().then((db) => {
        let transaction = db.transaction("subscription", "readonly");
        let subDb = transaction.objectStore("subscription");
        return wrapReq(subDb.get(1));
    });
}

self.addEventListener('message', async function (event) {
    if (event.data.action === "getCities") {
        console.log("getCities");
        let cities = await getCities();
        console.log(cities);
        event.ports[0].postMessage({
            error: null,
            cities: cities
        });
    } else if (event.data.action === "getSubscription") {
        let sub = await getSubscription();
        event.ports[0].postMessage({
            error: null,
            ...sub
        });
    } else if (event.data.action === "setSubscription") {
        await setSubscription(event.data.sub);
        event.ports[0].postMessage({
            error: null
        });
    }
});


self.addEventListener('push', async function (event) {
    const payload = event.data.json();
    if (payload.action === "confirm") {
        let resp = await fetch(payload.endpoint);
        let body;
        if (resp.ok) {
            let json = await resp.json();
            body = json.msg;
            if (json.cities !== undefined) {
                updateCities(json.cities);
            }
            if (json.type !== undefined && json.unsubscribe !== undefined) {
                updateSubscription(json.type, json.unsubscribe);
            }
        } else {
            body = "Odber notifikácii sa nepodarilo potvrdiť.";
        }

        event.waitUntil(
            self.registration.showNotification('Notifikácie o COVID-19 vakcinácii', {
                body: body,
                lang: "sk"
            })
        );
    } else if (payload.action === "notifySpots") {
        event.waitUntil(
            self.registration.showNotification('Voľné miesta na očkovanie', {
                body: payload.body,
                icon: payload.icon,
                actions: payload.actions,
                data: event.data.json(),
                lang: "sk"
            })
        );
    } else if (payload.action === "notifyGroups") {
        event.waitUntil(
            self.registration.showNotification('Nová skupina na očkovanie', {
                body: payload.body,
                icon: payload.icon,
                actions: payload.actions,
                data: event.data.json(),
                lang: "sk"
            })
        );
    } else if (payload.action === "notify") {
        event.waitUntil(
            self.registration.showNotification('Notifikácie o COVID-19 vakcinácii', {
                body: payload.body,
                icon: payload.icon,
                actions: payload.actions,
                data: event.data.json(),
                lang: "sk"
            })
        );
    }
});

self.addEventListener('notificationclick', async function (event) {
    if (!event.action) {
        return;
    }
    event.notification.close();
    const payload = event.notification.data;
    let url = payload.actionMap[event.action];
    event.waitUntil(clients.matchAll({type: 'window'}).then(clientsArr => {
        // If a Window tab matching the targeted URL already exists, focus that;
        const hadWindowToFocus = clientsArr.some(windowClient => windowClient.url === url ? (windowClient.focus(), true) : false);
        // Otherwise, open a new tab to the applicable URL and focus it.
        if (!hadWindowToFocus) clients.openWindow(url).then(windowClient => windowClient ? windowClient.focus() : null);
    }));
});

