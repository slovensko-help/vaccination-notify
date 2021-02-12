self.addEventListener('push', async function (event) {
    const payload = event.data.json();
    if (payload.action === "confirm") {
        let resp = await fetch(payload.endpoint);
        let body;
        if (resp.ok) {
            let json = await resp.json();
            body = json.msg;
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

