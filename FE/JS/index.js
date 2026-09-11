// ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
//            Default Variables
//  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
//   - JS 변수

// 서버 위치
var ServerDefaultUrl = `https://developer-hirehaul-dashboard.onrender.com/`;

// 요소들
var searchButton = document.getElementById('searchButton');
var searchInput = document.getElementById('searchInput');
var searchAction = document.getElementById('searchAction');
var searchFailed = document.getElementById('searchFailed');

var cards = document.getElementById('cards');

var tagButtons = document.querySelectorAll('.tag');
var tagBox = document.getElementById('tagBox');

// 필터를 저장하는 리스트
var tagClicked = [];

// 데이터를 받아두는 리스트
var cardList = [{id: 0, name: "Test Kaisya", text: "Test text"}];

var isInited = false;

// ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

// =========================================================================

// ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
//                Functions
//  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
//   - JS Util 함수

/** 요소들이 JS에 잘 인식 되는지 확인하는 함수
 * @returns {void} 없음
 */
function checkElements() {
    if(!searchButton) console.warn("검색 버튼이 null또는 undefined입니다.");
    if(!searchInput) console.warn("검색 텍스트 박스가 null또는 undefined입니다.");
    if(!searchAction) console.warn("검색 중 액션이 null또는 undefined입니다.");
    if(!searchFailed) console.warn("검색 실패 박스가 null또는 undefined입니다.");
    if(!cards) console.warn("카드 리스트 박스가 null또는 undefined입니다.");
    if(!tagButtons) console.warn("태그 버튼들이 null또는 undefined입니다.");
    console.log("요소 검사에 성공했습니다.");
}

/** 검색어를 받아서 검색하는 함수
 * @param {string} input 검색어
 * @returns {void} 없음
 */
function findWithTitle(input) {
    let isFound = false;
    searchAction.classList.remove('hide');
    searchAction.classList.remove('hide');
    searchAction.classList.add('hide');
    searchAction.classList.add('hide');
    cards.innerHTML = '';
    searchAction.classList.remove('hide');
    let searched = cardList.filter((card) => card.name.toLowerCase().includes(input));
    isFound = searched.length > 0;
    searchAction.classList.add('hide');
    if(!isFound) return searchFailed.classList.remove('hide');
    searched.forEach((card) => {
        // 요소
        let cardElement = document.createElement('div');
        cardElement.classList.add('card');

        // 타이틀
        (() => {
            let cardTitleBox = document.createElement('div');
            cardTitleBox.classList.add('cardTitleBox');
            // 타이틀 텍스트
            (() => {
                let cardTitle = document.createElement('h3');
                cardTitle.classList.add('cardTitle');
                cardTitle.textContent = card.name;
                cardTitleBox.appendChild(cardTitle);
            })();
            cardElement.appendChild(cardTitleBox);
        })();

        (() => {
            let cardTextBox = document.createElement('div');
            cardTextBox.classList.add('cardTextBox');
            cardTextBox.textContent = card.text;
            cardElement.appendChild(cardTextBox);
        })();

        // 요소 추가
        cards.appendChild(cardElement);
    });
}

// ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

// =========================================================================

// ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
//                  Events
//  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
//   - 요소에 Events 연결

// 검색 버튼
searchButton.addEventListener('click', () => {
    findWithTitle(searchInput.value);
});

// 엔터키
searchInput.addEventListener('keydown', (ev) => {
    if(ev.key !== "Enter") return;
    findWithTitle(searchInput.value);
});

// 웹에 접속했을 때
window.addEventListener('load', () => {
    checkElements();
    if(isInited) return;
    tagButtons.forEach((tagButton) => {
        let id = tagButton.lastElementChild.innerHTML;
        tagClicked[id] = false;
        tagButton.addEventListener('click', () => {
            let value = tagClicked[id];
            tagClicked[id] = !value;
            if (tagClicked[id]) {
                tagButton.firstElementChild.classList.add('boxClicked');
                tagButton.classList.add('tagClicked');
                tagBox.prepend(tagButton);
            } else {
                tagButton.firstElementChild.classList.remove('boxClicked');
                tagButton.classList.remove('tagClicked');
                tagBox.appendChild(tagButton);
            }
        });
    });
    isInited = true;

    // Dev
    const response = fetch(`${ServerDefaultUrl}/api/jobs`);
    if(!response.ok) { console.warn("정보 못 가져옴"); }
    console.log(response);
});

// ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛