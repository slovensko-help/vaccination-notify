// Fix preventDefault for IE
(function () {
    var workingDefaultPrevented = (function () {
        var e = document.createEvent('CustomEvent')
        e.initEvent('Bootstrap', true, true)
        e.preventDefault()
        return e.defaultPrevented
    })()
    if (!workingDefaultPrevented) {
        var origPreventDefault = Event.prototype.preventDefault
        Event.prototype.preventDefault = function () {
            if (!this.cancelable) {
                return
            }
            origPreventDefault.call(this)
            Object.defineProperty(this, 'defaultPrevented', {
                get: function () {
                    return true
                },
                configurable: true
            })
        }
    }
})()