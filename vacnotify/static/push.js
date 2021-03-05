function sendMessage(message) {
  return new Promise(function(resolve, reject) {
    var messageChannel = new MessageChannel();
    messageChannel.port1.onmessage = function(event) {
      if (event.data.error) {
        reject(event.data.error);
      } else {
        resolve(event.data);
      }
    };

    navigator.serviceWorker.controller.postMessage(message,
      [messageChannel.port2]);
  });
}


async function onPush(event) {
    let elem = $("#push_sub")
    elem.attr('required', 'required');
    $("#email").attr("required", null);
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
                onSubmit(null);
            }).catch((error) => {
                console.log(error);
            });
        }
    });
}