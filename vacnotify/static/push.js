async function onPush(event) {
    let elem = $("#push_sub")
    elem.attr('required', 'required');
    $("#email").attr("required", null);
    event.preventDefault();
    event.stopPropagation()
    await navigator.serviceWorker.getRegistration().then((registration) => {
        if (registration !== null) {
            return registration.pushManager.getSubscription().then((subscription) => {
                if (subscription !== null) {
                    elem.val(JSON.stringify(subscription));
                    onSubmit(null);
                } else {
                    let modal = new bootstrap.Modal(document.getElementById("push-modal"));
                    modal.show();
                }
            });
        }
    });
}

async function onNotificationRequest(event) {
    await navigator.serviceWorker.getRegistration().then((registration) => {
        if (registration) {
            registration.pushManager.getSubscription().then(async (subscription) => {
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
            }).then((subscription) => {
                $("#push_sub").val(JSON.stringify(subscription));
                onSubmit(null);
            }).catch((error) => {
                if ($("#push-requested").css("display") !== "none") {
                    $("#push-requested").fadeToggle(250, "swing", () => {
                        $("#push-denied").fadeToggle(250, "swing")
                    })
                }
            });
        }
    }).catch((error) => {
        console.log(error);
    });
}