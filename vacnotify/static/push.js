async function onPush(event) {
    console.log("HERE");
    let elem = $("#push_sub")
    elem.attr('required', 'required');
    $("#email").attr("required", null);
    let selectedCities = $.makeArray($("#cities input:checked").map((i, elem) => {return $(elem).val()}));
    event.preventDefault();
    event.stopPropagation()
    await navigator.serviceWorker.getRegistration().then((registration) => {
        if (registration !== null) {
            return registration.pushManager.getSubscription().then(async (subscription) => {
                if (subscription !== null) {
                    return subscription;
                } else {
                    const response = await fetch('/pubkey');
                    const vapidPublicKey = await response.text();
                    const convertedVapidKey = urlBase64ToUint8Array(vapidPublicKey);
                    return registration.pushManager.subscribe({
                        userVisibleOnly: true,
                        applicationServerKey: convertedVapidKey
                    });
                }
            }).then((subscription) => {
                elem.val(JSON.stringify(subscription));
                window.localStorage.selectedCities = JSON.stringify(selectedCities);
                onSubmit(null);
            }).catch((error) => {
                console.log(error);
            });
        }
    });
}