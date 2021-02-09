self.addEventListener('push', async function (event) {
    const payload = JSON.parse(event.data.text());
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
                lang: "sk"
            })
        );
    } else if (payload.action === "notifyGroups") {

    } else if (payload.action === "notify") {

    } else {
        // Unknown action, show something anyway?
    }
});

