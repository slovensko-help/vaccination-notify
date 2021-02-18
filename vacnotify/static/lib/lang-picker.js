
function Util(){};Util.hasClass=function(el,className){if(el.classList)return el.classList.contains(className);else return!!el.className.match(new RegExp('(\\s|^)'+className+'(\\s|$)'));};Util.addClass=function(el,className){var classList=className.split(' ');if(el.classList)el.classList.add(classList[0]);else if(!Util.hasClass(el,classList[0]))el.className+=" "+classList[0];if(classList.length>1)Util.addClass(el,classList.slice(1).join(' '));};Util.removeClass=function(el,className){var classList=className.split(' ');if(el.classList)el.classList.remove(classList[0]);else if(Util.hasClass(el,classList[0])){var reg=new RegExp('(\\s|^)'+classList[0]+'(\\s|$)');el.className=el.className.replace(reg,' ');}
    if(classList.length>1)Util.removeClass(el,classList.slice(1).join(' '));};Util.toggleClass=function(el,className,bool){if(bool)Util.addClass(el,className);else Util.removeClass(el,className);};Util.setAttributes=function(el,attrs){for(var key in attrs){el.setAttribute(key,attrs[key]);}};Util.getChildrenByClassName=function(el,className){var children=el.children,childrenByClass=[];for(var i=0;i<el.children.length;i++){if(Util.hasClass(el.children[i],className))childrenByClass.push(el.children[i]);}
    return childrenByClass;};Util.is=function(elem,selector){if(selector.nodeType){return elem===selector;}
    var qa=(typeof(selector)==='string'?document.querySelectorAll(selector):selector),length=qa.length,returnArr=[];while(length--){if(qa[length]===elem){return true;}}
    return false;};Util.setHeight=function(start,to,element,duration,cb){var change=to-start,currentTime=null;var animateHeight=function(timestamp){if(!currentTime)currentTime=timestamp;var progress=timestamp-currentTime;var val=parseInt((progress/duration)*change+start);element.style.height=val+"px";if(progress<duration){window.requestAnimationFrame(animateHeight);}else{cb();}};element.style.height=start+"px";window.requestAnimationFrame(animateHeight);};Util.scrollTo=function(final,duration,cb,scrollEl){var element=scrollEl||window;var start=element.scrollTop||document.documentElement.scrollTop,currentTime=null;if(!scrollEl)start=window.scrollY||document.documentElement.scrollTop;var animateScroll=function(timestamp){if(!currentTime)currentTime=timestamp;var progress=timestamp-currentTime;if(progress>duration)progress=duration;var val=Math.easeInOutQuad(progress,start,final-start,duration);element.scrollTo(0,val);if(progress<duration){window.requestAnimationFrame(animateScroll);}else{cb&&cb();}};window.requestAnimationFrame(animateScroll);};Util.moveFocus=function(element){if(!element)element=document.getElementsByTagName("body")[0];element.focus();if(document.activeElement!==element){element.setAttribute('tabindex','-1');element.focus();}};Util.getIndexInArray=function(array,el){return Array.prototype.indexOf.call(array,el);};Util.cssSupports=function(property,value){if('CSS'in window){return CSS.supports(property,value);}else{var jsProperty=property.replace(/-([a-z])/g,function(g){return g[1].toUpperCase();});return jsProperty in document.body.style;}};Util.extend=function(){var extended={};var deep=false;var i=0;var length=arguments.length;if(Object.prototype.toString.call(arguments[0])==='[object Boolean]'){deep=arguments[0];i++;}
    var merge=function(obj){for(var prop in obj){if(Object.prototype.hasOwnProperty.call(obj,prop)){if(deep&&Object.prototype.toString.call(obj[prop])==='[object Object]'){extended[prop]=extend(true,extended[prop],obj[prop]);}else{extended[prop]=obj[prop];}}}};for(;i<length;i++){var obj=arguments[i];merge(obj);}
    return extended;};Util.osHasReducedMotion=function(){if(!window.matchMedia)return false;var matchMediaObj=window.matchMedia('(prefers-reduced-motion: reduce)');if(matchMediaObj)return matchMediaObj.matches;return false;};if(!Element.prototype.matches){Element.prototype.matches=Element.prototype.msMatchesSelector||Element.prototype.webkitMatchesSelector;}
if(!Element.prototype.closest){Element.prototype.closest=function(s){var el=this;if(!document.documentElement.contains(el))return null;do{if(el.matches(s))return el;el=el.parentElement||el.parentNode;}while(el!==null&&el.nodeType===1);return null;};}
if(typeof window.CustomEvent!=="function"){function CustomEvent(event,params){params=params||{bubbles:false,cancelable:false,detail:undefined};var evt=document.createEvent('CustomEvent');evt.initCustomEvent(event,params.bubbles,params.cancelable,params.detail);return evt;}
    CustomEvent.prototype=window.Event.prototype;window.CustomEvent=CustomEvent;}
Math.easeInOutQuad=function(t,b,c,d){t/=d/2;if(t<1)return c/2*t*t+b;t--;return-c/2*(t*(t-2)-1)+b;};Math.easeInQuart=function(t,b,c,d){t/=d;return c*t*t*t*t+b;};Math.easeOutQuart=function(t,b,c,d){t/=d;t--;return-c*(t*t*t*t-1)+b;};Math.easeInOutQuart=function(t,b,c,d){t/=d/2;if(t<1)return c/2*t*t*t*t+b;t-=2;return-c/2*(t*t*t*t-2)+b;};Math.easeOutElastic=function(t,b,c,d){var s=1.70158;var p=d*0.7;var a=c;if(t==0)return b;if((t/=d)==1)return b+c;if(!p)p=d*.3;if(a<Math.abs(c)){a=c;var s=p/4;}
else var s=p/(2*Math.PI)*Math.asin(c/a);return a*Math.pow(2,-10*t)*Math.sin((t*d-s)*(2*Math.PI)/p)+c+b;};(function(){var focusTab=document.getElementsByClassName('js-tab-focus');function detectClick(){if(focusTab.length>0){resetFocusTabs(false);window.addEventListener('keydown',detectTab);}
    window.removeEventListener('mousedown',detectClick);};function detectTab(event){if(event.keyCode!==9)return;resetFocusTabs(true);window.removeEventListener('keydown',detectTab);window.addEventListener('mousedown',detectClick);};function resetFocusTabs(bool){var outlineStyle=bool?'':'none';for(var i=0;i<focusTab.length;i++){focusTab[i].style.setProperty('outline',outlineStyle);}};window.addEventListener('mousedown',detectClick);}());

(function() {
    var LanguagePicker = function(element) {
        this.element = element;
        this.select = this.element.getElementsByTagName('select')[0];
        this.options = this.select.getElementsByTagName('option');
        this.selectedOption = getSelectedOptionText(this);
        this.pickerId = this.select.getAttribute('id');
        this.trigger = false;
        this.dropdown = false;
        this.firstLanguage = false;
        this.arrowSvgPath = '<svg viewBox="0 0 16 16"><polygon points="3,5 8,11 13,5 "></polygon></svg>';

        initLanguagePicker(this);
        initLanguagePickerEvents(this);
    };

    function initLanguagePicker(picker) {
        // create the HTML for the custom dropdown element
        picker.element.insertAdjacentHTML('beforeend', initButtonPicker(picker) + initListPicker(picker));

        // save picker elements
        picker.dropdown = picker.element.getElementsByClassName('language-picker__dropdown')[0];
        picker.languages = picker.dropdown.getElementsByClassName('language-picker__item');
        picker.firstLanguage = picker.languages[0];

        for( var i = 0; i < picker.languages.length; i++) {
            if (picker.languages[i].getAttribute('aria-selected') === 'true')
            {
                picker.firstLanguage = picker.languages[i];
            }
        }
        picker.trigger = picker.element.getElementsByClassName('language-picker__button')[0];
    };

    function initLanguagePickerEvents(picker) {
        // make sure to add the icon class to the arrow dropdown inside the button element
        var svgs = picker.trigger.getElementsByTagName('svg');
        Util.addClass(svgs[0], 'icon');
        // language selection in dropdown
        // ⚠️ Important: you need to modify this function in production
        initLanguageSelection(picker);

        // click events
        picker.trigger.addEventListener('click', function(){
            toggleLanguagePicker(picker, false);
        });
        // keyboard navigation
        picker.dropdown.addEventListener('keydown', function(event){
            if(event.keyCode && event.keyCode == 38 || event.key && event.key.toLowerCase() == 'arrowup') {
                keyboardNavigatePicker(picker, 'prev');
            } else if(event.keyCode && event.keyCode == 40 || event.key && event.key.toLowerCase() == 'arrowdown') {
                keyboardNavigatePicker(picker, 'next');
            }
        });
    };

    function toggleLanguagePicker(picker, bool) {
        var ariaExpanded;
        if(bool) {
            ariaExpanded = bool;
        } else {
            ariaExpanded = picker.trigger.getAttribute('aria-expanded') == 'true' ? 'false' : 'true';
        }
        picker.trigger.setAttribute('aria-expanded', ariaExpanded);
        if(ariaExpanded == 'true') {
            picker.firstLanguage.focus(); // fallback if transition is not supported
            picker.dropdown.addEventListener('transitionend', function cb(){
                picker.firstLanguage.focus();
                picker.dropdown.removeEventListener('transitionend', cb);
            });
            // place dropdown
            placeDropdown(picker);
        }
    };

    function placeDropdown(picker) {
        var triggerBoundingRect = picker.trigger.getBoundingClientRect();
        Util.toggleClass(picker.dropdown, 'language-picker__dropdown--right', (window.innerWidth < triggerBoundingRect.left + picker.dropdown.offsetWidth));
        Util.toggleClass(picker.dropdown, 'language-picker__dropdown--up', (window.innerHeight < triggerBoundingRect.bottom + picker.dropdown.offsetHeight));
    };

    function checkLanguagePickerClick(picker, target) { // if user clicks outside the language picker -> close it
        if( !picker.element.contains(target) ) toggleLanguagePicker(picker, 'false');
    };

    function moveFocusToPickerTrigger(picker) {
        if(picker.trigger.getAttribute('aria-expanded') == 'false') return;
        if(document.activeElement.closest('.language-picker__dropdown') == picker.dropdown) picker.trigger.focus();
    };

    function initButtonPicker(picker) { // create the button element -> picker trigger
        // check if we need to add custom classes to the button trigger
        var customClasses = picker.element.getAttribute('data-trigger-class') ? ' '+picker.element.getAttribute('data-trigger-class') : '';

        var button = '<button class="language-picker__button'+customClasses+'" aria-label="'+picker.select.value+' '+picker.element.getElementsByTagName('label')[0].textContent+'" aria-expanded="false" aria-controls="'+picker.pickerId+'-dropdown">';
        button = button + '<span aria-hidden="true" class="language-picker__label language-picker__flag language-picker__flag--'+picker.select.value+'">'+picker.selectedOption+'';
        button = button +picker.arrowSvgPath+'</span>';
        return button+'</button>';
    };

    function initListPicker(picker) { // create language picker dropdown
        var list = '<div class="language-picker__dropdown" aria-describedby="'+picker.pickerId+'-description" id="'+picker.pickerId+'-dropdown">';
        list = list + '<p class="sr-only" id="'+picker.pickerId+'-description">'+picker.element.getElementsByTagName('label')[0].textContent+'</p>';
        list = list + '<ul class="language-picker__list" role="listbox">';
        for(var i = 0; i < picker.options.length; i++) {
            var selected = picker.options[i].hasAttribute('selected') ? ' aria-selected="true"' : '',
                language = picker.options[i].getAttribute('lang');
            list = list + '<li><a lang="'+language+'" hreflang="'+language+'" href="'+getLanguageUrl(picker.options[i])+'"'+selected+' role="option" data-value="'+picker.options[i].value+'" class="govuk-link language-picker__item language-picker__flag language-picker__flag--'+picker.options[i].value+'"><span>'+picker.options[i].text+'</span></a></li>';
        };
        return list;
    };

    function getSelectedOptionText(picker) { // used to initialize the label of the picker trigger button
        var label = '';
        if('selectedIndex' in picker.select) {
            label = picker.options[picker.select.selectedIndex].text;
        } else {
            label = picker.select.querySelector('option[selected]').text;
        }
        return label;
    };

    function getLanguageUrl(option) {
        return option.getAttribute('data-url');
    };

    function initLanguageSelection(picker) {
        picker.element.getElementsByClassName('language-picker__list')[0].addEventListener('click', function(event){
            var language = event.target.closest('.language-picker__item');
            if(!language) return;

            if(language.hasAttribute('aria-selected') && language.getAttribute('aria-selected') == 'true') {
                // selecting the same language
                event.preventDefault();
                picker.trigger.setAttribute('aria-expanded', 'false'); // hide dropdown
            } else {
                // ⚠️ Important: this 'else' code needs to be removed in production.
                // The user has to be redirected to the new url -> nothing to do here
                //event.preventDefault();
                //picker.element.getElementsByClassName('language-picker__list')[0].querySelector('[aria-selected="true"]').removeAttribute('aria-selected');
                //language.setAttribute('aria-selected', 'true');
                //picker.trigger.getElementsByClassName('language-picker__label')[0].setAttribute('class', 'language-picker__label language-picker__flag language-picker__flag--'+language.getAttribute('data-value'));
                //picker.trigger.getElementsByClassName('language-picker__label')[0].getElementsByTagName('em')[0].textContent = language.textContent;
                //picker.trigger.setAttribute('aria-expanded', 'false');
            }
        });
    };

    function keyboardNavigatePicker(picker, direction) {
        var index = Util.getIndexInArray(picker.languages, document.activeElement);
        index = (direction == 'next') ? index + 1 : index - 1;
        if(index < 0) index = picker.languages.length - 1;
        if(index >= picker.languages.length) index = 0;
        Util.moveFocus(picker.languages[index]);
    };

    //initialize the LanguagePicker objects
    var languagePicker = document.getElementsByClassName('js-language-picker');
    if( languagePicker.length > 0 ) {
        var pickerArray = [];
        for( var i = 0; i < languagePicker.length; i++) {
            (function(i){pickerArray.push(new LanguagePicker(languagePicker[i]));})(i);
        }

        // listen for key events
        window.addEventListener('keyup', function(event){
            if( event.keyCode && event.keyCode == 27 || event.key && event.key.toLowerCase() == 'escape' ) {
                // close language picker on 'Esc'
                pickerArray.forEach(function(element){
                    moveFocusToPickerTrigger(element); // if focus is within dropdown, move it to dropdown trigger
                    toggleLanguagePicker(element, 'false'); // close dropdown
                });
            }
        });
        // close language picker when clicking outside it
        window.addEventListener('click', function(event){
            pickerArray.forEach(function(element){
                checkLanguagePickerClick(element, event.target);
            });
        });
    }
}());