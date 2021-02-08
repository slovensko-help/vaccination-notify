function urlBase64ToUint8Array(base64String) {
    let padding = '='.repeat((4 - base64String.length % 4) % 4);
    let base64 = (base64String + padding)
        .replace(/\-/g, '+')
        .replace(/_/g, '/');
    console.log(base64);
    let rawData = window.atob(base64);
    let outputArray = new Uint8Array(rawData.length);

    for (let i = 0; i < rawData.length; ++i) {
        outputArray[i] = rawData.charCodeAt(i);
    }
    return outputArray;
}

let swReg = null;
let pushSub = null;

if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js', {scope: '/'}).then(function (registration) {
        swReg = registration;
        registration.pushManager.getSubscription((subscription) => {
           pushSub = subscription;
        });
    }, function (error) {
        console.log('Service worker registration failed:', error);
    });
} else {
    console.log('Service workers are not supported.');
}

/*
navigator.serviceWorker.ready
    .then((registration) => {
        swReg = registration;
        return registration.pushManager.getSubscription()
            .then(async (subscription) => {
                if (subscription) {
                    return subscription;
                }
                const response = await fetch('/pubkey');
                const vapidPublicKey = await response.text();
                const convertedVapidKey = urlBase64ToUint8Array(vapidPublicKey);
                return registration.pushManager.subscribe({
                    userVisibleOnly: true,
                    applicationServerKey: convertedVapidKey
                });
            });
    }).then((subscription) => {
    pushSub = subscription;
});*/