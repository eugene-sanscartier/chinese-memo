import html
import json
import os
import re
from urllib.parse import unquote
import numpy.random
import hashlib
import glob

import pandas

from hanzipy.decomposer import HanziDecomposer

decomposer = HanziDecomposer()

import re

_re_number = re.compile(r'\d')

import genanki

# import strokes2svg

CSS = """
#card-body {
    font: 17px/1.85em 'Avenir Next'; /* tightened line-height */
    text-align: justify;
    margin-top: 50px;
    margin-bottom: 60px;
}

.acentersmall {
    line-height: 1.25em; /* further reduce spacing for compact blocks */
}

.content {
    padding-left: 0.5em;
    border-left: 4px solid transparent;
}

.header {
    font: bold 17px/1.5em;
    padding-left: 0.5em;
}

.header-red {
    border-left: 4px solid #db4437;
    color: #db4437;
}

.header-green {
    border-left: 4px solid #0f9d58;
    color: #0f9d58;
}

.header-blue {
    border-left: 4px solid #4285f4;
    color: #4285f4;
}

.header-yellow {
    border-left: 4px solid #f4b400;
    color: #f4b400;
}

.genuine-cloze[show-state="hint"] {
    border-bottom: 2px solid #ff5c82;
    background-color: #ff96af;
}

.pseudo-cloze[show-state="hint"] {
    border-bottom: 2px solid #4285f4;
    background-color: #87b1ff;
}

#show-one-cloze-left,
#show-one-cloze-right,
#no-more-cloze {
    height: 100%;
    position: fixed;
    z-index: 9;
    top: 0;
    background-color: rgba(66, 133, 244, 0.15);
}

#show-one-cloze-left {
    left: 0;
}

#show-one-cloze-right {
    right: 0;
}

#no-more-cloze {
    width: 10px;
    background-color: #db4437;
    left: 0;
    display: none;
}

#show-all-pseudo-clozes {
    height: 20px;
    width: 100%;
    position: fixed;
    z-index: 9;
    top: 0;
    left: 0;
    background-color: transparent;
}

.mobile ol,
.mobile ul,
.mobile li {
    margin-left: -0.5em;
}

.mobile li {
    margin: 0.1em, inherit;
}

table {
    border-collapse: collapse;
    margin: 0.5em;
}

thead tr,
tfoot tr {
    border-top: 2px solid #0f9d58;
    border-bottom: 2px solid #0f9d58;
}

td,
th {
    border: 1px solid #0f9d58;
    padding: 0.3em 0.5em;
}

hr {
    border-top: 1px solid #aaaaaa;
    width: 100%;
    margin: 0;
    padding: 0;
}

pre {
    border-left: 2px solid #0f9d58;
    padding-left: 10px;
}

code,
kbd,
var,
samp,
tt {
    background-color: #fdf3d6;
}

.disable-select {
    -webkit-touch-callout: none;
    user-select: none;
}

/* Center all clozes in a single vertical column */
#enhanced-clozes {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: flex-start;
}
#enhanced-clozes .genuine-cloze,
#enhanced-clozes .pseudo-cloze {
    display: block;
    text-align: center;
    max-width: 600px; /* limit width for readability */
    box-sizing: border-box;
    margin: 4px 0;
}
"""

# Cloze model front template (Enhanced Cloze)
front_template = r'''<!-- VERSION 1.14 -->
<script>
    var scrollToClozeOnToggle = true
    var animateScroll = false
    var showHintsForPseudoClozes = true
    var underlineRevealedPseudoClozes = false
    var underlineRevealedGenuineClozes = true
    var revealPseudoClozesByDefault = false
    var swapLeftAndRightBorderActions = true
    var revealNextGenuineClozeShortcut = "J"
    var revealPreviousGenuineClozeShortcut = "H"
    var revealAllGenuineClozesShortcut = "Shift+J"
    var revealNextPseudoClozeShortcut = "N"
    var revealAllPseudoClozesShortcut = "Shift+N"
    var clozeWidthPercent = 85
</script>
<!-- CONFIG END -->

<div id="card-body">
    <div id="title-section" style="text-align: center; font-size: 24px; font-weight: bold; margin-bottom: 20px; ">
        {{Title}}
    </div>
    <div id="main-section" class="content">
        <span id="enhanced-clozes"></span>
    </div>
    <div id="loci-section" style="margin-top:20px;">
        {{Loci}}
    </div>
    <div id="functional-elements">
        <div id="show-one-cloze-left"></div>
        <div id="show-one-cloze-right"></div>
        <div id="no-more-cloze"></div>
    </div>
</div>

<!-- ENHANCED_CLOZE -->
<span id="enhanced-cloze-content" style="display:none">{{Content}}</span>
<span style="display:none;" id="edit-clozes">{{edit:cloze:Content}}</span>
<span style="display:none">{{cloze:Content}}</span>
<span style="display:none">{{cloze:Cloze99}}</span>

<script>
    var enhancedClozesData = {
        "clozeId": [],
        "answers": [],
        "hints": [],
    }

    var genuineClozeOrder = []
    var currentGenuineIndex = -1

    async function enhancedClozesMain() {

        // Regex for clozes
        // the extra (?:) at the beginning is there so that Anki doesn't think this is a field
        const clozeRegex = /{(?:){c(\d+)::([\W\w]*?)(?:::([\W\w]*?))?}}/g

        var ctrlDown = false;

        await maybeInjectJquery()
        defineEnhancedClozeAddEventListener()
        setupKeyListenerForCtrlKey()
        prepareEnhancedClozesData()
        prepareEnhancedClozesHTML()
        maybeScrollToFirstGenuineCloze()
        setupClozeEvents()
        setupEditFieldDuringReview()
        insertStyling()

        function prepareEnhancedClozesData() {
            var content = document.getElementById("enhanced-cloze-content").innerHTML
            var match = clozeRegex.exec(content);
            while (match != null) {
                enhancedClozesData["clozeId"].push(match[1])
                enhancedClozesData["answers"].push(match[2])
                enhancedClozesData["hints"].push(match[3] !== undefined ? match[3] : "")
                match = clozeRegex.exec(content);
            }
        }

        function prepareEnhancedClozesHTML() {
            var ord =
                `{{#c1}}1{{/c1}}{{#c2}}2{{/c2}}{{#c3}}3{{/c3}}{{#c4}}4{{/c4}}{{#c5}}5{{/c5}}`
            ord = ord.trim()

            // create html with enhanced-clozes and insert it into the enhanced-clozes element
            var content = document.getElementById("enhanced-cloze-content").innerHTML
            var html = ""
            var ctr = 0
            var prevLastIndex = 0
            match = clozeRegex.exec(content);
            while (match !== null) {
                var startIdx = clozeRegex.lastIndex - match[0].length
                html += content.slice(prevLastIndex, startIdx)

                var clozeType = ord == enhancedClozesData["clozeId"][ctr] ? "genuine-cloze" : "pseudo-cloze"
                html +=
                    `<span class="${clozeType}" show-state="hint" cid="${enhancedClozesData["clozeId"][ctr]}" index="${ctr}">${enhancedClozesData["hints"][ctr]}</span>`

                prevLastIndex = clozeRegex.lastIndex
                match = clozeRegex.exec(content);
                ctr += 1
            }
            html += content.slice(prevLastIndex)

            var enhDiv = document.getElementById("enhanced-clozes")
            enhDiv.innerHTML = html

            // genuine clozes refer to those belong to current card and need to be answered, e.g. { {c2::abc} } on card2
            // pseudo clozes refer to the opposite, e.g. { {c1::abc} } and { {c3::abc} } on card2
            $('.genuine-cloze, .pseudo-cloze').each(function (index, elem) {
                toggleCloze(elem, 'hint')
            });


            $('.pseudo-cloze').css('cursor', 'pointer')
            $('.genuine-cloze').css('cursor', 'pointer')
            $('#show-one-cloze-left').css('cursor', 'pointer')
            $('#show-one-cloze-right').css('cursor', 'pointer')

            genuineClozeOrder = Array.from(document.querySelectorAll('.genuine-cloze'))

            // this prevents the blue selection briefly showing up on mobile when tapping on a cloze
            $('.pseudo-cloze').addClass('disable-select')
            $('.genuine-cloze').addClass('disable-select')
            $('#show-one-cloze-left').addClass('disable-select')
            $('#show-one-cloze-right').addClass('disable-select')
        }

        function maybeScrollToFirstGenuineCloze() {
            if ($('.genuine-cloze').length != 0) {
                maybeScrollToCloze($('.genuine-cloze').first().get(0));
            }
        }


        function setupClozeEvents() {
            // we are not using enhancedClozeAddEventListener (which prevents duplicate event listeners) so we need to
            // make sure that the listeners are only added once using the firstTimeLoadingEnhancedCloze variable
            if (typeof firstTimeLoadingEnhancedCloze === 'undefined') {
                firstTimeLoadingEnhancedCloze = false
                if (/webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator
                    .userAgent)) {
                    setupIOsClozeClickEvents()
                } else {
                    setupDesktopAndAndroidClozeClickEvents()
                }
            }

            setupClozeKeyEvents()
        }
        function setupDesktopAndAndroidClozeClickEvents() {
            $(document).on('click', '.pseudo-cloze', function (event) {
                toggleCloze(event.target, 'toggle');
            });

            $(document).on('click', '.genuine-cloze', function (event) {
                toggleCloze(event.target, 'toggle');
            });

            $(document).on('click', '#show-one-cloze-left', function (event) {
                revealPreviousClozeAndScroll();
            });

            $(document).on('click', '#show-one-cloze-right', function (event) {
                revealNextClozeAndScroll();
            });
        }

        function setupIOsClozeClickEvents() {
            // For ios click events don't work, so we use a custom click handler
            addMobileClickHandler(
                '.pseudo-cloze',
                function (event) {
                    toggleCloze(event.target, 'toggle');
                }
            )
            addMobileClickHandler(
                '.genuine-cloze',
                function (event) {
                    toggleCloze(event.target, 'toggle');
                }
            )
            addMobileClickHandler(
                '#show-one-cloze-left',
                function (event) {
                    revealPreviousClozeAndScroll();
                }
            )
            addMobileClickHandler(
                '#show-one-cloze-right',
                function (event) {
                    revealNextClozeAndScroll();
                }
            )
        }

        function refreshGenuineClozeOrder() {
            genuineClozeOrder = Array.from(document.querySelectorAll('.genuine-cloze'))
        }

        function setClozeState(clozeElem, state) {
            if (!clozeElem) return
            toggleCloze(clozeElem, state)
        }

        function scrollToClozeTop(clozeElem) {
            if (!clozeElem) return
            $('html, body').animate({
                scrollTop: $(clozeElem).offset().top - 10
            }, animateScroll ? 500 : 0)
        }

        function scrollToClozeBottom(clozeElem) {
            if (!clozeElem) return
            var target = $(clozeElem).offset().top + $(clozeElem).outerHeight() - $(window).height() + 10
            $('html, body').animate({
                scrollTop: Math.max(0, target)
            }, animateScroll ? 500 : 0)
        }

        function revealNextClozeAndScroll() {
            refreshGenuineClozeOrder()
            if (genuineClozeOrder.length === 0) return

            var targetIndex = Math.min(currentGenuineIndex + 1, genuineClozeOrder.length - 1)
            if (targetIndex === currentGenuineIndex) {
                var rightBorder = document.getElementById('show-one-cloze-right')
                rightBorder.classList.add('blink-red')
                setTimeout(function() { rightBorder.classList.remove('blink-red') }, 1000)
                return
            }

            var keepOpen = new Set()
            keepOpen.add(targetIndex)
            if (targetIndex - 1 >= 0) keepOpen.add(targetIndex - 1)

            genuineClozeOrder.forEach(function (cloze, idx) {
                if (keepOpen.has(idx)) {
                    setClozeState(cloze, 'answer')
                } else {
                    setClozeState(cloze, 'hint')
                }
            })

            currentGenuineIndex = targetIndex
            scrollToClozeBottom(genuineClozeOrder[targetIndex])
        }

        function revealPreviousClozeAndScroll() {
            refreshGenuineClozeOrder()
            if (genuineClozeOrder.length === 0) return

            var targetIndex = Math.max(currentGenuineIndex - 1, 0)
            if (targetIndex === currentGenuineIndex) {
                var leftBorder = document.getElementById('show-one-cloze-left')
                leftBorder.classList.add('blink-red')
                setTimeout(function() { leftBorder.classList.remove('blink-red') }, 1000)
                return
            }
            var keepOpen = new Set()
            keepOpen.add(targetIndex)
            if (targetIndex + 1 < genuineClozeOrder.length) keepOpen.add(targetIndex + 1)

            genuineClozeOrder.forEach(function (cloze, idx) {
                if (keepOpen.has(idx)) {
                    setClozeState(cloze, 'answer')
                } else {
                    setClozeState(cloze, 'hint')
                }
            })

            currentGenuineIndex = targetIndex
            scrollToClozeTop(genuineClozeOrder[targetIndex])
        }

        function addMobileClickHandler(selector, callback) {
            // "click" events don't work on AnkiMobile, this is a workaround.
            // This uses touchstart and touchend events to detect a click.
            // If the touchend position is close enough to the touchstart position,
            // the callback is called.

            // This is the maximum distance the touchend position can differ from the touchstart position
            // to still be considered a click
            const distanceThreshold = 10;
            // Stores the last touchstart position
            let touchStartPosition = null;

            $(document).on('touchstart', selector, function (event) {
                const touches = event.originalEvent.touches;
                if (touches.length === 1) {
                    const touch = touches[0];
                    touchStartPosition = {
                        x: touch.clientX,
                        y: touch.clientY
                    };
                } else {
                    touchStartPosition = null;
                }

            });

            $(document).on('touchend', selector, function (event) {
                const changedTouches = event.originalEvent.changedTouches;
                if (touchStartPosition && changedTouches.length === 1) {
                    const changedTouch = changedTouches[0];
                    const touchEndX = changedTouch.clientX;
                    const touchEndY = changedTouch.clientY;
                    const diffX = Math.abs(touchStartPosition.x - touchEndX);
                    const diffY = Math.abs(touchStartPosition.y - touchEndY);
                    if (diffX < distanceThreshold && diffY < distanceThreshold) {
                        callback(event);
                    }
                }

                touchStartPosition = null;
            });
        }

        function setupClozeKeyEvents() {
            window.enhancedClozeAddEventListener("keydown", (event) => {
                if (shortcutMatcher(revealNextGenuineClozeShortcut)(event)) {
                    revealNextClozeAndScroll();
                }
                if (shortcutMatcher(revealPreviousGenuineClozeShortcut)(event)) {
                    revealPreviousClozeAndScroll();
                }
                if (shortcutMatcher(revealAllGenuineClozesShortcut)(event)) {
                    toggleAllClozesOfAType("genuine")
                }
                if (shortcutMatcher(revealNextPseudoClozeShortcut)(event)) {
                    revealOneClozeOfAType("pseudo");
                }
                if (shortcutMatcher(revealAllPseudoClozesShortcut)(event)) {
                    toggleAllClozesOfAType("pseudo");
                }
            })
        }



        function setupEditFieldDuringReview() {
            moveEditClozesElm()

            $("#enhanced-clozes").off('click').on('click', function (event) {
                if (document.getElementsByClassName("EFDRC-outline").length == 0) return
                if (!ctrlDown) return
                activateEditFieldDuringReview()
            });

            function moveEditClozesElm() {
                var editClozesElm = document.getElementById("edit-clozes")
                document.getElementById("main-section").appendChild(editClozesElm)
            }

            function activateEditFieldDuringReview() {
                var enhancedClozesElm = document.getElementById("enhanced-clozes")
                var editClozesElm = document.getElementById("edit-clozes")
                if (["inline", ""].includes(enhancedClozesElm.style.display)) {
                    enhancedClozesElm.style.display = "none";
                    editClozesElm.style.display = "inline";
                } else {
                    enhancedClozesElm.style.display = "inline";
                    editClozesElm.style.display = "none";
                }
                setTimeout(() => {
                    editable = editClozesElm.getElementsByClassName(
                        "EFDRC-outline")[0]
                    editable.onfocus()
                    editable.focus()
                })
            }

        }

        function insertStyling() {
            if (document.getElementById("enhanced-clozes-style")) return;

            mainSection = document.getElementById("main-section")
            style = document.createElement("style")

            // Calculate touch border width based on cloze width
            var touchBorderWidthPercent = (100 - clozeWidthPercent) / 2

            // this css is also in the css file, but inserting the css here is easier than updating the css file for all users
            style.id = "enhanced-clozes-style"
            style.innerHTML = `
                .disable-select {
                    -webkit-touch-callout: none;
                    user-select: none;
                }
                #show-one-cloze-left {
                    width: ${touchBorderWidthPercent}%;
                }
                #show-one-cloze-right {
                    width: ${touchBorderWidthPercent}%;
                }
                #enhanced-clozes .genuine-cloze,
                #enhanced-clozes .pseudo-cloze {
                    width: ${clozeWidthPercent}%;
                }
            `

            if (underlineRevealedPseudoClozes) {
                style.innerHTML += `
                .pseudo-cloze {
                    border-bottom: 1px solid #4285f4;
                    padding-bottom: 1px;
                }`
            }
            if (underlineRevealedGenuineClozes) {
                style.innerHTML += `
                .genuine-cloze {
                    border-bottom: 1px solid #ff5c82;
                    padding-bottom: 1px;
                }`
            }
            style.innerHTML += `
                @keyframes blinkRed {
                    0%, 100% { background-color: rgba(66, 133, 244, 0.15); }
                    50% { background-color: rgba(219, 68, 55, 0.5); }
                }
                .blink-red {
                    animation: blinkRed 0.5s ease-in-out 2;
                }
            `
            mainSection.insertBefore(style, mainSection.children[0])
        }

        function revealOneClozeOfAType(clozeType) {
            if (!["genuine", "pseudo"].includes(clozeType)) {
                console.log(`clozeType has unexpected value: ${clozeType}`)
            }

            if (!$(`.${clozeType}-cloze[show-state="hint"]`).length) {
                $('#no-more-cloze').animate({
                    display: "toggle",
                }, 500);
                return
            }

            var hiddenClozes = $(`.${clozeType}-cloze[show-state="hint"]`)
            if (hiddenClozes.length != 0) {
                revealCloze(hiddenClozes[0]);
            }
        }

        function toggleAllClozesOfAType(clozeType) {
            if (!["genuine", "pseudo"].includes(clozeType)) {
                console.log(`clozeType has unexpected value: ${clozeType}`)
            }

            var allRevealed = !$(`.${clozeType}-cloze[show-state="hint"`).length
            $(`.${clozeType}-cloze`).each(function (index, elem) {
                toggleCloze(elem, allRevealed ? "hint" : "answer");
            })
        }

        function revealCloze(elem) {
            if (!isVisible(elem)) {
                maybeScrollToCloze(elem);
            } else {
                toggleCloze(elem, 'answer');
                if (!isVisible(elem)) {
                    maybeScrollToCloze(elem);
                } else { }
                $(elem).hide(0);
                $(elem).fadeIn(500);
            }
        }

        function isVisible(elm) {
            var rect = elm.getBoundingClientRect();
            var viewHeight = Math.max(document.documentElement.clientHeight, window.innerHeight);
            return !(rect.bottom < 0 || rect.top - viewHeight >= 0);
        }

        function maybeScrollToCloze(elem) {
            if (!scrollToClozeOnToggle) return
            $('html, body').animate({
                scrollTop: $(elem).offset().top - 60
            }, animateScroll ? 500 : 0);
        }

        function defineEnhancedClozeAddEventListener() {
            // define enhancedClozeAddEventListener
            // this function is almost identical to `document.addEventListener`
            // but removes the event listener attached on previous card / front side
            // using this function
            if (typeof window.enhancedClozeEventListener != "undefined") {
                for (const listener of window.enhancedClozeEventListener) {
                    const type = listener[0]
                    const handler = listener[1]
                    document.removeEventListener(type, handler)
                }
            }
            window.enhancedClozeEventListener = []

            window.enhancedClozeAddEventListener = function (type, handler) {
                document.addEventListener(type, handler)
                window.enhancedClozeEventListener.push([type, handler])
            }
        }

        var specialCharCodes = {
            "-": "minus",
            "=": "equal",
            "[": "bracketleft",
            "]": "bracketright",
            ";": "semicolon",
            "'": "quote",
            "`": "backquote",
            "\\": "backslash",
            ",": "comma",
            ".": "period",
            "/": "slash",
        };

        // Returns function that match keyboard event to see if it matches given shortcut.
        function shortcutMatcher(shortcut) {
            var shortcutKeys = shortcut.toLowerCase().split(/[+]/).map(key => key.trim())
            var mainKey = shortcutKeys[shortcutKeys.length - 1]
            if (mainKey.length === 1) {
                if (/\d/.test(mainKey)) {
                    mainKey = "digit" + mainKey
                } else if (/[a-zA-Z]/.test(mainKey)) {
                    mainKey = "key" + mainKey
                } else {
                    var code = specialCharCodes[mainKey];
                    if (code) {
                        mainKey = code
                    }
                }
            }
            var ctrl = shortcutKeys.includes("ctrl")
            var shift = shortcutKeys.includes("shift")
            var alt = shortcutKeys.includes("alt")

            var matchShortcut = function (ctrl, shift, alt, mainKey, event) {
                if (event.originalEvent !== undefined) {
                    event = event.originalEvent
                }
                if (mainKey !== event.code.toLowerCase()) return false
                if (ctrl !== (event.ctrlKey || event.metaKey)) return false
                if (shift !== event.shiftKey) return false
                if (alt !== event.altKey) return false
                return true
            }.bind(window, ctrl, shift, alt, mainKey)

            return matchShortcut
        }

        function setupKeyListenerForCtrlKey() {
            window.enhancedClozeAddEventListener("keydown", function (ev) {
                if (isCtrlKey(ev.code)) ctrlDown = true;
            })
            window.enhancedClozeAddEventListener("keyup", function (ev) {
                if (isCtrlKey(ev.code)) ctrlDown = false;
            })
        }


        function isCtrlKey(keycode) {
            return ['ControlLeft', 'MetaLeft'].includes(keycode)
        }

        function showNextElement(elem) {
            $(elem).next().show(0);
        };

        async function maybeInjectJquery() {
            if (typeof jQuery === "undefined") {
                await injectScript("_jquery.min.js");
            }
        }

        async function injectScript(src) {
            return new Promise((resolve, reject) => {
                const script = document.createElement('script');
                script.src = src;
                script.async = true;
                script.onload = resolve;
                script.onerror = (event) => {
                    reject(new Error(`Script load error for source: ${src}`));
                };
                document.head.appendChild(script);
            });
        };

    }

    // This function is defined outside of enhancedClozesMain because it is used on the back side of the card as well
    function toggleCloze(elem, displayOption) {

        if (elem == null) return

        // if the element is not a cloze get its ancestor cloze
        if (elem.classList.contains("genuine-cloze") || elem.classList.contains("pseudo-cloze"))
            cloze = elem
        else {
            cloze = $(elem).closest(".genuine-cloze")
            if (cloze == null)
                cloze = $(elem).closest(".pseudo-cloze")
        }

        var index = $(cloze).attr('index');
        var answer = enhancedClozesData["answers"][index]
        var hint = enhancedClozesData["hints"][index]

        if (!showHintsForPseudoClozes && cloze.classList.contains('pseudo-cloze')) {
            hint = ""
        }

        if (revealPseudoClozesByDefault || answer.startsWith('#')) {
            if (answer.startsWith('#')) {
                answer = answer.slice(1)
            }

            if ($(cloze).attr('class') == 'pseudo-cloze') {
                $(cloze).attr('show-state', 'answer');
                $(cloze).html(answer);
                return
            }
        }

        if (displayOption == 'answer' || (displayOption == 'toggle' && $(cloze).attr('show-state') == 'hint')) {
            $(cloze).attr('show-state', 'answer');
            $(cloze).html(answer);
        } else if (displayOption == 'hint' || (displayOption == 'toggle' && $(cloze).attr('show-state') == 'answer')) {
            $(cloze).attr('show-state', 'hint');
            hint = '&nbsp;&nbsp;[&nbsp;&nbsp;' + hint + '&nbsp;&nbsp;]&nbsp;&nbsp;';
            $(cloze).html(hint);
        }

        // rerun mathjax on the document so that the cloze text gets formatted
        // ... for MathJax 2
        try {
            MathJax.Hub.Queue(["Typeset", MathJax.Hub]);
        } catch { }
        // ... for MathJax 3
        try {
            MathJax.typesetPromise()
        } catch { }

    }

    enhancedClozesMain()
</script>
'''

# Back template (Enhanced Cloze)
back_template = r'''
{{FrontSide}}
<script>
// Back side: reveal every cloze (genuine + pseudo)
setTimeout(function(){
  document.querySelectorAll('.genuine-cloze,.pseudo-cloze').forEach(function(el){
    try { toggleCloze(el,'answer'); } catch(e) { el.setAttribute('show-state','answer'); }
  });
},0);
</script>
'''

with open("memo.json", "r", encoding="utf-8") as file_obj:
    memo_data = json.load(file_obj)

def build_cloze_note(radical_key, guid, radical_entrys, loci_key="", loci_name="", loci_range=None):
    """Build a single cloze note for all characters in a radical group"""

    # Create title text with loci metadata
    if loci_range:
        length = loci_range[1] - loci_range[0] + 1
        # look if ther is a number at the end of the string and if yes store it in a viariable and remove it
        match = re.search(r'(\d+)\s*$', loci_key)
        if match: loci_key = loci_key[:match.start()].rstrip() + f' #{int(match.group(1))}'

        title_text = f"{loci_key} <br> {loci_name} <br> [{loci_range[0]}-{loci_range[1]}] ({length})"

    # Build the cloze text with all characters
    cloze_text = ""
    note_text = ""

    # Get loci image for this loci group (all entries share same loci)
    first_entry = radical_entrys[0]
    img, loci_name = get_image_file(radical_key, loci_data, first_entry["position"], first_entry["character"])
    locus_info = f"{loci_key}<br>" + loci_name
    loci_html = f'<div class="acentersmall" style="text-align:center">{locus_info}</div><br>'
    loci_html += f'<div class="image" style="text-align:center;"><img src="{img.split("/")[-1]}"></div><br>'

    for idx, entry in enumerate(radical_entrys, start=1):
        char = entry["character"]
        pinyin_data = entry["pinyin"]
        pinyin_str = pinyin_data["pinyin"]
        gloss = entry["gloss"]
        gloss_fr = entry["gloss_fr"]

        hint = entry["hint"]

        subcomponents = entry["subcomponents"]
        subcomponents_fr = entry["subcomponents_fr"]

        # Build decomposition HTML in gen_anki_device.py style
        decomp_html = ""
        if "components" in entry and entry["components"]:
            decomp_html += '<div class="acentersmall" style="text-align:left;"><strong>Decomposition:</strong><br>'
            for component in entry["components"]:
                component_gloss_str = f'{component["gloss_fr"]} [{component["gloss"]}]'
                decomp_html += f'<div style="margin-top:2px;text-align:left;margin-left:5%;"><strong>━</strong> {component["character"]} ({component_gloss_str})'
                if "hint" in component and component["hint"] and component["hint"] not in ["None", ""]:
                    decomp_html += f"[Hint: {component['hint']}]"
                decomp_html += "<br></div>"

            if not (len(subcomponents_fr) == 1 and component["character"] in list(subcomponents_fr)[0]):
                subcomp_str = ""
                for subcomponent in list(subcomponents_fr.items()):
                    sub_key, sub_value = subcomponent[0], subcomponent[1]
                    subcomp_str += f"{sub_key}({sub_value}); "
                if subcomp_str:
                    decomp_html += f'<div style="margin-top:2px;text-align:left;margin-left:10%;"><strong>●</strong> {subcomp_str}<br></div>'

        hint_html = ""
        if hint and hint != "":
            hint_html += '<div class="acentersmall" style="text-align:left;"><strong>Hint:</strong><br>'
            hint_html += f'<div style="margin-top:2px;text-align:left;margin-left:5%;"><strong>━</strong> {hint}<br></div>'
            hint_html += '</div>'

        gloss_html = ""
        gloss_html += f'<div class="acentersmall" style="text-align:left;"><strong>Gloss:</strong></div>'
        gloss_html += f'<div style="margin-top:2px;text-align:left;margin-left:5%;"><strong>━</strong> {gloss_fr} [{gloss}]</div>'

        char_html = ""
        char_html += f'<div style="font-size:45px;text-align:center;margin-top:25px;">{char}</div>'
        char_html += f'<div class="acentersmall"><strong>P</strong>: {entry["position"]} / <strong>R</strong>: {entry["rank"]} / <strong>C</strong>: {float(entry["coverage"]):.2f}%</div><br>'

        # Build detailed pinyin breakdown like gen_anki_device.py
        pinyin_initial = pinyin_data["initial"]
        pinyin_final = pinyin_data["final"]
        pinyin_tone = pinyin_data["tone"]
        u_is_v = pinyin_data["u_is_v"]

        pinyin_detailed = '<div class="acentersmall" style="text-align:left;"><strong>Pinyin:</strong><br>'
        pinyin_detailed += f'<div style="margin-top:2px;text-align:left;margin-left:5%;"><strong>━</strong> {pinyin_str}<br></div>'

        if pinyin_initial != "":
            pinyin_detailed += f'<div style="margin-top:2px;text-align:left;margin-left:10%;"><strong>●</strong> <strong>[{pinyin_initial}]</strong> - {memo_data["initials"][pinyin_initial]}<br></div>'

        if pinyin_final in memo_data["finals"]:
            action_str = f"{memo_data['finals'][pinyin_final]['action']}({memo_data['finals'][pinyin_final]['image']})"
            pinyin_detailed += f'<div style="margin-top:2px;text-align:left;margin-left:10%;"><strong>●</strong> <strong>[{pinyin_final}]</strong> - {action_str}<br></div>'
        else:
            pinyin_detailed += f'<div style="margin-top:2px;text-align:left;margin-left:10%;"><strong>●</strong> <strong>[{pinyin_final}]</strong> - {memo_data["initials"][pinyin_final]}<br></div>'

        pinyin_detailed += f'<div style="margin-top:2px;text-align:left;margin-left:10%;"><strong>●</strong> <strong>[{memo_data["tones"][pinyin_tone]["symbol"]}]</strong> - {memo_data["tones"][pinyin_tone]["view"]}'
        if u_is_v:
            pinyin_detailed += f" - <strong>[{memo_data['tones']['6']['symbol']}]</strong>"
        pinyin_detailed += "<br></div>"
        pinyin_detailed += "</div>"

        # Answer formatted like gen_anki_device.py
        answer_html = char_html
        answer_html += pinyin_detailed
        answer_html += gloss_html
        answer_html += hint_html
        answer_html += decomp_html
        answer_html += "</div><br>"

        # Create cloze deletion - all use c1 to appear on same card; use position as hint
        cloze_text += f"{{{{c1::{answer_html}::{entry['position']}}}}} "

    # Create the model
    model_id = int(hashlib.sha256(("Cloze-Model-Device").encode()).hexdigest(), 16) % (1 << 16)
    model = genanki.Model(model_id, f'Cloze-Model-Device', fields=[{
        'name': 'Title'
    }, {
        'name': 'Content'
    }, {
        'name': 'Note'
    }, {
        'name': 'Loci'
    }], templates=[{
        'name': 'Cloze',
        'qfmt': front_template,
        'afmt': back_template,
    }], css=CSS, model_type=genanki.Model.CLOZE)

    # Create the note
    note = genanki.Note(model=model, fields=[title_text, cloze_text, note_text, loci_html], guid=guid)

    return note


def get_loci_key(radical_key: str, position: int, char: str, loci_data: dict) -> str:
    """Determine which loci key a character belongs to based on its radical and position"""
    special = ["㇒雨虫", "𠂇囗丿田礻耳", "衤巾", "⺊又⺈勹饣"]

    if radical_key in special:
        radical = decomposer.decompose(char, 2)["components"][0]
        return radical

    for loci, loci_info in loci_data.items():
        if loci.startswith(radical_key):
            if loci_info["range"][0] <= position <= loci_info["range"][1]:
                return loci

    return radical_key  # fallback to radical if no loci found


def get_image_file(key: str, loci_data: dict, k: int, char: str):
    img_file = ""

    special = ["㇒雨虫", "𠂇囗丿田礻耳", "衤巾", "⺊又⺈勹饣"]
    if key in special:
        radical = decomposer.decompose(char, 2)["components"][0]  # pyright: ignore[reportOptionalSubscript, reportCallIssue, reportArgumentType]

        img_file = f"loci/{radical}.png"
        loci_name = loci_data.get(radical, {}).get("name", "")
        return img_file, loci_name

    for loci, loci_info in loci_data.items():
        if loci.startswith(key):
            if loci_info["range"][0] <= k <= loci_info["range"][1]:

                loci_name = loci_data.get(loci, {}).get("name", "")

                if loci[0] == "㇇":
                    loci = "㇇" + loci[-1]
                img_file = f"loci/{loci}.png"

                break

    return img_file, loci_name


with open("data_memodevice.json", "r", encoding="utf-8") as file_obj:
    dict_entries = json.load(file_obj)

with open("loci.json", "r", encoding="utf-8") as file_obj:
    loci_data = json.load(file_obj)

# open guid txt list
with open("guids.txt", "r", encoding="utf-8") as file_obj:
    guid_list = [line.strip() for line in file_obj.readlines()]

counter_list = []

if __name__ == "__main__":
    entries, decks = [], []

    # Reorganize entries by loci instead of radical
    loci_groups = {}
    deck_counter = 0

    for radical_key, radical_entrys in dict_entries.items():
        for entry in radical_entrys:
            # Determine which loci this character belongs to
            loci_key = get_loci_key(radical_key, entry["position"], entry["character"], loci_data)

            if loci_key not in loci_groups:
                loci_groups[loci_key] = {"radical_key": radical_key, "entries": []}

            loci_groups[loci_key]["entries"].append(entry)

    # Create decks and notes grouped by loci
    for m, (loci_key, loci_group) in enumerate(loci_groups.items()):
        radical_key = loci_group["radical_key"]
        loci_entrys = loci_group["entries"]

        # Get loci name and range for deck title
        loci_info = loci_data.get(loci_key, {})
        loci_name = loci_info.get("name", loci_key)
        loci_range = loci_info.get("range", [])

        if loci_range:
            range_str = f"[{loci_range[0]}-{loci_range[1]}]"
            length = loci_range[1] - loci_range[0] + 1
            deck_title = f'Character Set::{m+1:03d} {loci_key[0]} - {range_str} ({length}): {loci_name}'
            counter_list += [{'set': m + 1, 'loci': loci_key[0], 'name': loci_name, 'length': length}]

        deck = genanki.Deck(20594000000 + m + 1, deck_title)
        decks.append(deck)

        print(f"Processing: {loci_key[0]:5}; Loci {m+1}/{len(loci_groups)}; {len(loci_entrys)} chars")

        # Create one cloze note for all characters in this loci group
        cloze_note = build_cloze_note(radical_key, guid_list[m], loci_entrys, loci_key, loci_name, loci_range)
        deck.add_note(cloze_note)

    package = genanki.Package(decks)
    package.media_files = glob.glob("loci/*.png")

    package.write_to_file('memo_anki.apkg')

    with pandas.ExcelWriter(f"memo_sets.xlsx") as writer:
        df = pandas.DataFrame(counter_list)
        df.to_excel(writer, sheet_name="Loci Sets", index=False)
        writer.sheets["Loci Sets"].autofit()
