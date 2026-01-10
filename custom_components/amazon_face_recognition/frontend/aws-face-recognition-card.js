function t(t,e,i,s){var n,o=arguments.length,r=o<3?e:null===s?s=Object.getOwnPropertyDescriptor(e,i):s;if("object"==typeof Reflect&&"function"==typeof Reflect.decorate)r=Reflect.decorate(t,e,i,s);else for(var l=t.length-1;l>=0;l--)(n=t[l])&&(r=(o<3?n(r):o>3?n(e,i,r):n(e,i))||r);return o>3&&r&&Object.defineProperty(e,i,r),r}"function"==typeof SuppressedError&&SuppressedError;
/**
 * @license
 * Copyright 2019 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */
const e=window,i=e.ShadowRoot&&(void 0===e.ShadyCSS||e.ShadyCSS.nativeShadow)&&"adoptedStyleSheets"in Document.prototype&&"replace"in CSSStyleSheet.prototype,s=Symbol(),n=new WeakMap;class o{constructor(t,e,i){if(this._$cssResult$=!0,i!==s)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=t,this.t=e}get styleSheet(){let t=this.o;const e=this.t;if(i&&void 0===t){const i=void 0!==e&&1===e.length;i&&(t=n.get(e)),void 0===t&&((this.o=t=new CSSStyleSheet).replaceSync(this.cssText),i&&n.set(e,t))}return t}toString(){return this.cssText}}const r=(t,...e)=>{const i=1===t.length?t[0]:e.reduce((e,i,s)=>e+(t=>{if(!0===t._$cssResult$)return t.cssText;if("number"==typeof t)return t;throw Error("Value passed to 'css' function must be a 'css' function result: "+t+". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.")})(i)+t[s+1],t[0]);return new o(i,t,s)},l=i?t=>t:t=>t instanceof CSSStyleSheet?(t=>{let e="";for(const i of t.cssRules)e+=i.cssText;return(t=>new o("string"==typeof t?t:t+"",void 0,s))(e)})(t):t;
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */var a;const h=window,d=h.trustedTypes,c=d?d.emptyScript:"",u=h.reactiveElementPolyfillSupport,p={toAttribute(t,e){switch(e){case Boolean:t=t?c:null;break;case Object:case Array:t=null==t?t:JSON.stringify(t)}return t},fromAttribute(t,e){let i=t;switch(e){case Boolean:i=null!==t;break;case Number:i=null===t?null:Number(t);break;case Object:case Array:try{i=JSON.parse(t)}catch(t){i=null}}return i}},_=(t,e)=>e!==t&&(e==e||t==t),v={attribute:!0,type:String,converter:p,reflect:!1,hasChanged:_},g="finalized";class $ extends HTMLElement{constructor(){super(),this._$Ei=new Map,this.isUpdatePending=!1,this.hasUpdated=!1,this._$El=null,this._$Eu()}static addInitializer(t){var e;this.finalize(),(null!==(e=this.h)&&void 0!==e?e:this.h=[]).push(t)}static get observedAttributes(){this.finalize();const t=[];return this.elementProperties.forEach((e,i)=>{const s=this._$Ep(i,e);void 0!==s&&(this._$Ev.set(s,i),t.push(s))}),t}static createProperty(t,e=v){if(e.state&&(e.attribute=!1),this.finalize(),this.elementProperties.set(t,e),!e.noAccessor&&!this.prototype.hasOwnProperty(t)){const i="symbol"==typeof t?Symbol():"__"+t,s=this.getPropertyDescriptor(t,i,e);void 0!==s&&Object.defineProperty(this.prototype,t,s)}}static getPropertyDescriptor(t,e,i){return{get(){return this[e]},set(s){const n=this[t];this[e]=s,this.requestUpdate(t,n,i)},configurable:!0,enumerable:!0}}static getPropertyOptions(t){return this.elementProperties.get(t)||v}static finalize(){if(this.hasOwnProperty(g))return!1;this[g]=!0;const t=Object.getPrototypeOf(this);if(t.finalize(),void 0!==t.h&&(this.h=[...t.h]),this.elementProperties=new Map(t.elementProperties),this._$Ev=new Map,this.hasOwnProperty("properties")){const t=this.properties,e=[...Object.getOwnPropertyNames(t),...Object.getOwnPropertySymbols(t)];for(const i of e)this.createProperty(i,t[i])}return this.elementStyles=this.finalizeStyles(this.styles),!0}static finalizeStyles(t){const e=[];if(Array.isArray(t)){const i=new Set(t.flat(1/0).reverse());for(const t of i)e.unshift(l(t))}else void 0!==t&&e.push(l(t));return e}static _$Ep(t,e){const i=e.attribute;return!1===i?void 0:"string"==typeof i?i:"string"==typeof t?t.toLowerCase():void 0}_$Eu(){var t;this._$E_=new Promise(t=>this.enableUpdating=t),this._$AL=new Map,this._$Eg(),this.requestUpdate(),null===(t=this.constructor.h)||void 0===t||t.forEach(t=>t(this))}addController(t){var e,i;(null!==(e=this._$ES)&&void 0!==e?e:this._$ES=[]).push(t),void 0!==this.renderRoot&&this.isConnected&&(null===(i=t.hostConnected)||void 0===i||i.call(t))}removeController(t){var e;null===(e=this._$ES)||void 0===e||e.splice(this._$ES.indexOf(t)>>>0,1)}_$Eg(){this.constructor.elementProperties.forEach((t,e)=>{this.hasOwnProperty(e)&&(this._$Ei.set(e,this[e]),delete this[e])})}createRenderRoot(){var t;const s=null!==(t=this.shadowRoot)&&void 0!==t?t:this.attachShadow(this.constructor.shadowRootOptions);return((t,s)=>{i?t.adoptedStyleSheets=s.map(t=>t instanceof CSSStyleSheet?t:t.styleSheet):s.forEach(i=>{const s=document.createElement("style"),n=e.litNonce;void 0!==n&&s.setAttribute("nonce",n),s.textContent=i.cssText,t.appendChild(s)})})(s,this.constructor.elementStyles),s}connectedCallback(){var t;void 0===this.renderRoot&&(this.renderRoot=this.createRenderRoot()),this.enableUpdating(!0),null===(t=this._$ES)||void 0===t||t.forEach(t=>{var e;return null===(e=t.hostConnected)||void 0===e?void 0:e.call(t)})}enableUpdating(t){}disconnectedCallback(){var t;null===(t=this._$ES)||void 0===t||t.forEach(t=>{var e;return null===(e=t.hostDisconnected)||void 0===e?void 0:e.call(t)})}attributeChangedCallback(t,e,i){this._$AK(t,i)}_$EO(t,e,i=v){var s;const n=this.constructor._$Ep(t,i);if(void 0!==n&&!0===i.reflect){const o=(void 0!==(null===(s=i.converter)||void 0===s?void 0:s.toAttribute)?i.converter:p).toAttribute(e,i.type);this._$El=t,null==o?this.removeAttribute(n):this.setAttribute(n,o),this._$El=null}}_$AK(t,e){var i;const s=this.constructor,n=s._$Ev.get(t);if(void 0!==n&&this._$El!==n){const t=s.getPropertyOptions(n),o="function"==typeof t.converter?{fromAttribute:t.converter}:void 0!==(null===(i=t.converter)||void 0===i?void 0:i.fromAttribute)?t.converter:p;this._$El=n,this[n]=o.fromAttribute(e,t.type),this._$El=null}}requestUpdate(t,e,i){let s=!0;void 0!==t&&(((i=i||this.constructor.getPropertyOptions(t)).hasChanged||_)(this[t],e)?(this._$AL.has(t)||this._$AL.set(t,e),!0===i.reflect&&this._$El!==t&&(void 0===this._$EC&&(this._$EC=new Map),this._$EC.set(t,i))):s=!1),!this.isUpdatePending&&s&&(this._$E_=this._$Ej())}async _$Ej(){this.isUpdatePending=!0;try{await this._$E_}catch(t){Promise.reject(t)}const t=this.scheduleUpdate();return null!=t&&await t,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){var t;if(!this.isUpdatePending)return;this.hasUpdated,this._$Ei&&(this._$Ei.forEach((t,e)=>this[e]=t),this._$Ei=void 0);let e=!1;const i=this._$AL;try{e=this.shouldUpdate(i),e?(this.willUpdate(i),null===(t=this._$ES)||void 0===t||t.forEach(t=>{var e;return null===(e=t.hostUpdate)||void 0===e?void 0:e.call(t)}),this.update(i)):this._$Ek()}catch(t){throw e=!1,this._$Ek(),t}e&&this._$AE(i)}willUpdate(t){}_$AE(t){var e;null===(e=this._$ES)||void 0===e||e.forEach(t=>{var e;return null===(e=t.hostUpdated)||void 0===e?void 0:e.call(t)}),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(t)),this.updated(t)}_$Ek(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$E_}shouldUpdate(t){return!0}update(t){void 0!==this._$EC&&(this._$EC.forEach((t,e)=>this._$EO(e,this[e],t)),this._$EC=void 0),this._$Ek()}updated(t){}firstUpdated(t){}}
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */
var m;$[g]=!0,$.elementProperties=new Map,$.elementStyles=[],$.shadowRootOptions={mode:"open"},null==u||u({ReactiveElement:$}),(null!==(a=h.reactiveElementVersions)&&void 0!==a?a:h.reactiveElementVersions=[]).push("1.6.3");const f=window,y=f.trustedTypes,A=y?y.createPolicy("lit-html",{createHTML:t=>t}):void 0,b="$lit$",x=`lit$${(Math.random()+"").slice(9)}$`,w="?"+x,C=`<${w}>`,S=document,E=()=>S.createComment(""),N=t=>null===t||"object"!=typeof t&&"function"!=typeof t,R=Array.isArray,k="[ \t\n\f\r]",H=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,T=/-->/g,U=/>/g,P=RegExp(`>|${k}(?:([^\\s"'>=/]+)(${k}*=${k}*(?:[^ \t\n\f\r"'\`<>=]|("|')|))|$)`,"g"),O=/'/g,z=/"/g,M=/^(?:script|style|textarea|title)$/i,I=Symbol.for("lit-noChange"),j=Symbol.for("lit-nothing"),D=new WeakMap,W=S.createTreeWalker(S,129,null,!1);function L(t,e){if(!Array.isArray(t)||!t.hasOwnProperty("raw"))throw Error("invalid template strings array");return void 0!==A?A.createHTML(e):e}class B{constructor({strings:t,_$litType$:e},i){let s;this.parts=[];let n=0,o=0;const r=t.length-1,l=this.parts,[a,h]=((t,e)=>{const i=t.length-1,s=[];let n,o=2===e?"<svg>":"",r=H;for(let e=0;e<i;e++){const i=t[e];let l,a,h=-1,d=0;for(;d<i.length&&(r.lastIndex=d,a=r.exec(i),null!==a);)d=r.lastIndex,r===H?"!--"===a[1]?r=T:void 0!==a[1]?r=U:void 0!==a[2]?(M.test(a[2])&&(n=RegExp("</"+a[2],"g")),r=P):void 0!==a[3]&&(r=P):r===P?">"===a[0]?(r=null!=n?n:H,h=-1):void 0===a[1]?h=-2:(h=r.lastIndex-a[2].length,l=a[1],r=void 0===a[3]?P:'"'===a[3]?z:O):r===z||r===O?r=P:r===T||r===U?r=H:(r=P,n=void 0);const c=r===P&&t[e+1].startsWith("/>")?" ":"";o+=r===H?i+C:h>=0?(s.push(l),i.slice(0,h)+b+i.slice(h)+x+c):i+x+(-2===h?(s.push(void 0),e):c)}return[L(t,o+(t[i]||"<?>")+(2===e?"</svg>":"")),s]})(t,e);if(this.el=B.createElement(a,i),W.currentNode=this.el.content,2===e){const t=this.el.content,e=t.firstChild;e.remove(),t.append(...e.childNodes)}for(;null!==(s=W.nextNode())&&l.length<r;){if(1===s.nodeType){if(s.hasAttributes()){const t=[];for(const e of s.getAttributeNames())if(e.endsWith(b)||e.startsWith(x)){const i=h[o++];if(t.push(e),void 0!==i){const t=s.getAttribute(i.toLowerCase()+b).split(x),e=/([.?@])?(.*)/.exec(i);l.push({type:1,index:n,name:e[2],strings:t,ctor:"."===e[1]?Y:"?"===e[1]?X:"@"===e[1]?J:q})}else l.push({type:6,index:n})}for(const e of t)s.removeAttribute(e)}if(M.test(s.tagName)){const t=s.textContent.split(x),e=t.length-1;if(e>0){s.textContent=y?y.emptyScript:"";for(let i=0;i<e;i++)s.append(t[i],E()),W.nextNode(),l.push({type:2,index:++n});s.append(t[e],E())}}}else if(8===s.nodeType)if(s.data===w)l.push({type:2,index:n});else{let t=-1;for(;-1!==(t=s.data.indexOf(x,t+1));)l.push({type:7,index:n}),t+=x.length-1}n++}}static createElement(t,e){const i=S.createElement("template");return i.innerHTML=t,i}}function V(t,e,i=t,s){var n,o,r,l;if(e===I)return e;let a=void 0!==s?null===(n=i._$Co)||void 0===n?void 0:n[s]:i._$Cl;const h=N(e)?void 0:e._$litDirective$;return(null==a?void 0:a.constructor)!==h&&(null===(o=null==a?void 0:a._$AO)||void 0===o||o.call(a,!1),void 0===h?a=void 0:(a=new h(t),a._$AT(t,i,s)),void 0!==s?(null!==(r=(l=i)._$Co)&&void 0!==r?r:l._$Co=[])[s]=a:i._$Cl=a),void 0!==a&&(e=V(t,a._$AS(t,e.values),a,s)),e}class Z{constructor(t,e){this._$AV=[],this._$AN=void 0,this._$AD=t,this._$AM=e}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(t){var e;const{el:{content:i},parts:s}=this._$AD,n=(null!==(e=null==t?void 0:t.creationScope)&&void 0!==e?e:S).importNode(i,!0);W.currentNode=n;let o=W.nextNode(),r=0,l=0,a=s[0];for(;void 0!==a;){if(r===a.index){let e;2===a.type?e=new F(o,o.nextSibling,this,t):1===a.type?e=new a.ctor(o,a.name,a.strings,this,t):6===a.type&&(e=new G(o,this,t)),this._$AV.push(e),a=s[++l]}r!==(null==a?void 0:a.index)&&(o=W.nextNode(),r++)}return W.currentNode=S,n}v(t){let e=0;for(const i of this._$AV)void 0!==i&&(void 0!==i.strings?(i._$AI(t,i,e),e+=i.strings.length-2):i._$AI(t[e])),e++}}class F{constructor(t,e,i,s){var n;this.type=2,this._$AH=j,this._$AN=void 0,this._$AA=t,this._$AB=e,this._$AM=i,this.options=s,this._$Cp=null===(n=null==s?void 0:s.isConnected)||void 0===n||n}get _$AU(){var t,e;return null!==(e=null===(t=this._$AM)||void 0===t?void 0:t._$AU)&&void 0!==e?e:this._$Cp}get parentNode(){let t=this._$AA.parentNode;const e=this._$AM;return void 0!==e&&11===(null==t?void 0:t.nodeType)&&(t=e.parentNode),t}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(t,e=this){t=V(this,t,e),N(t)?t===j||null==t||""===t?(this._$AH!==j&&this._$AR(),this._$AH=j):t!==this._$AH&&t!==I&&this._(t):void 0!==t._$litType$?this.g(t):void 0!==t.nodeType?this.$(t):(t=>R(t)||"function"==typeof(null==t?void 0:t[Symbol.iterator]))(t)?this.T(t):this._(t)}k(t){return this._$AA.parentNode.insertBefore(t,this._$AB)}$(t){this._$AH!==t&&(this._$AR(),this._$AH=this.k(t))}_(t){this._$AH!==j&&N(this._$AH)?this._$AA.nextSibling.data=t:this.$(S.createTextNode(t)),this._$AH=t}g(t){var e;const{values:i,_$litType$:s}=t,n="number"==typeof s?this._$AC(t):(void 0===s.el&&(s.el=B.createElement(L(s.h,s.h[0]),this.options)),s);if((null===(e=this._$AH)||void 0===e?void 0:e._$AD)===n)this._$AH.v(i);else{const t=new Z(n,this),e=t.u(this.options);t.v(i),this.$(e),this._$AH=t}}_$AC(t){let e=D.get(t.strings);return void 0===e&&D.set(t.strings,e=new B(t)),e}T(t){R(this._$AH)||(this._$AH=[],this._$AR());const e=this._$AH;let i,s=0;for(const n of t)s===e.length?e.push(i=new F(this.k(E()),this.k(E()),this,this.options)):i=e[s],i._$AI(n),s++;s<e.length&&(this._$AR(i&&i._$AB.nextSibling,s),e.length=s)}_$AR(t=this._$AA.nextSibling,e){var i;for(null===(i=this._$AP)||void 0===i||i.call(this,!1,!0,e);t&&t!==this._$AB;){const e=t.nextSibling;t.remove(),t=e}}setConnected(t){var e;void 0===this._$AM&&(this._$Cp=t,null===(e=this._$AP)||void 0===e||e.call(this,t))}}class q{constructor(t,e,i,s,n){this.type=1,this._$AH=j,this._$AN=void 0,this.element=t,this.name=e,this._$AM=s,this.options=n,i.length>2||""!==i[0]||""!==i[1]?(this._$AH=Array(i.length-1).fill(new String),this.strings=i):this._$AH=j}get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}_$AI(t,e=this,i,s){const n=this.strings;let o=!1;if(void 0===n)t=V(this,t,e,0),o=!N(t)||t!==this._$AH&&t!==I,o&&(this._$AH=t);else{const s=t;let r,l;for(t=n[0],r=0;r<n.length-1;r++)l=V(this,s[i+r],e,r),l===I&&(l=this._$AH[r]),o||(o=!N(l)||l!==this._$AH[r]),l===j?t=j:t!==j&&(t+=(null!=l?l:"")+n[r+1]),this._$AH[r]=l}o&&!s&&this.j(t)}j(t){t===j?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,null!=t?t:"")}}class Y extends q{constructor(){super(...arguments),this.type=3}j(t){this.element[this.name]=t===j?void 0:t}}const K=y?y.emptyScript:"";class X extends q{constructor(){super(...arguments),this.type=4}j(t){t&&t!==j?this.element.setAttribute(this.name,K):this.element.removeAttribute(this.name)}}class J extends q{constructor(t,e,i,s,n){super(t,e,i,s,n),this.type=5}_$AI(t,e=this){var i;if((t=null!==(i=V(this,t,e,0))&&void 0!==i?i:j)===I)return;const s=this._$AH,n=t===j&&s!==j||t.capture!==s.capture||t.once!==s.once||t.passive!==s.passive,o=t!==j&&(s===j||n);n&&this.element.removeEventListener(this.name,this,s),o&&this.element.addEventListener(this.name,this,t),this._$AH=t}handleEvent(t){var e,i;"function"==typeof this._$AH?this._$AH.call(null!==(i=null===(e=this.options)||void 0===e?void 0:e.host)&&void 0!==i?i:this.element,t):this._$AH.handleEvent(t)}}class G{constructor(t,e,i){this.element=t,this.type=6,this._$AN=void 0,this._$AM=e,this.options=i}get _$AU(){return this._$AM._$AU}_$AI(t){V(this,t)}}const Q=f.litHtmlPolyfillSupport;
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */
var tt;null==Q||Q(B,F),(null!==(m=f.litHtmlVersions)&&void 0!==m?m:f.litHtmlVersions=[]).push("2.8.0");const et=window,it=et.trustedTypes,st=it?it.createPolicy("lit-html",{createHTML:t=>t}):void 0,nt="$lit$",ot=`lit$${(Math.random()+"").slice(9)}$`,rt="?"+ot,lt=`<${rt}>`,at=document,ht=()=>at.createComment(""),dt=t=>null===t||"object"!=typeof t&&"function"!=typeof t,ct=Array.isArray,ut="[ \t\n\f\r]",pt=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,_t=/-->/g,vt=/>/g,gt=RegExp(`>|${ut}(?:([^\\s"'>=/]+)(${ut}*=${ut}*(?:[^ \t\n\f\r"'\`<>=]|("|')|))|$)`,"g"),$t=/'/g,mt=/"/g,ft=/^(?:script|style|textarea|title)$/i,yt=(t=>(e,...i)=>({_$litType$:t,strings:e,values:i}))(1),At=Symbol.for("lit-noChange"),bt=Symbol.for("lit-nothing"),xt=new WeakMap,wt=at.createTreeWalker(at,129,null,!1);function Ct(t,e){if(!Array.isArray(t)||!t.hasOwnProperty("raw"))throw Error("invalid template strings array");return void 0!==st?st.createHTML(e):e}const St=(t,e)=>{const i=t.length-1,s=[];let n,o=2===e?"<svg>":"",r=pt;for(let e=0;e<i;e++){const i=t[e];let l,a,h=-1,d=0;for(;d<i.length&&(r.lastIndex=d,a=r.exec(i),null!==a);)d=r.lastIndex,r===pt?"!--"===a[1]?r=_t:void 0!==a[1]?r=vt:void 0!==a[2]?(ft.test(a[2])&&(n=RegExp("</"+a[2],"g")),r=gt):void 0!==a[3]&&(r=gt):r===gt?">"===a[0]?(r=null!=n?n:pt,h=-1):void 0===a[1]?h=-2:(h=r.lastIndex-a[2].length,l=a[1],r=void 0===a[3]?gt:'"'===a[3]?mt:$t):r===mt||r===$t?r=gt:r===_t||r===vt?r=pt:(r=gt,n=void 0);const c=r===gt&&t[e+1].startsWith("/>")?" ":"";o+=r===pt?i+lt:h>=0?(s.push(l),i.slice(0,h)+nt+i.slice(h)+ot+c):i+ot+(-2===h?(s.push(void 0),e):c)}return[Ct(t,o+(t[i]||"<?>")+(2===e?"</svg>":"")),s]};class Et{constructor({strings:t,_$litType$:e},i){let s;this.parts=[];let n=0,o=0;const r=t.length-1,l=this.parts,[a,h]=St(t,e);if(this.el=Et.createElement(a,i),wt.currentNode=this.el.content,2===e){const t=this.el.content,e=t.firstChild;e.remove(),t.append(...e.childNodes)}for(;null!==(s=wt.nextNode())&&l.length<r;){if(1===s.nodeType){if(s.hasAttributes()){const t=[];for(const e of s.getAttributeNames())if(e.endsWith(nt)||e.startsWith(ot)){const i=h[o++];if(t.push(e),void 0!==i){const t=s.getAttribute(i.toLowerCase()+nt).split(ot),e=/([.?@])?(.*)/.exec(i);l.push({type:1,index:n,name:e[2],strings:t,ctor:"."===e[1]?Tt:"?"===e[1]?Pt:"@"===e[1]?Ot:Ht})}else l.push({type:6,index:n})}for(const e of t)s.removeAttribute(e)}if(ft.test(s.tagName)){const t=s.textContent.split(ot),e=t.length-1;if(e>0){s.textContent=it?it.emptyScript:"";for(let i=0;i<e;i++)s.append(t[i],ht()),wt.nextNode(),l.push({type:2,index:++n});s.append(t[e],ht())}}}else if(8===s.nodeType)if(s.data===rt)l.push({type:2,index:n});else{let t=-1;for(;-1!==(t=s.data.indexOf(ot,t+1));)l.push({type:7,index:n}),t+=ot.length-1}n++}}static createElement(t,e){const i=at.createElement("template");return i.innerHTML=t,i}}function Nt(t,e,i=t,s){var n,o,r,l;if(e===At)return e;let a=void 0!==s?null===(n=i._$Co)||void 0===n?void 0:n[s]:i._$Cl;const h=dt(e)?void 0:e._$litDirective$;return(null==a?void 0:a.constructor)!==h&&(null===(o=null==a?void 0:a._$AO)||void 0===o||o.call(a,!1),void 0===h?a=void 0:(a=new h(t),a._$AT(t,i,s)),void 0!==s?(null!==(r=(l=i)._$Co)&&void 0!==r?r:l._$Co=[])[s]=a:i._$Cl=a),void 0!==a&&(e=Nt(t,a._$AS(t,e.values),a,s)),e}class Rt{constructor(t,e){this._$AV=[],this._$AN=void 0,this._$AD=t,this._$AM=e}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(t){var e;const{el:{content:i},parts:s}=this._$AD,n=(null!==(e=null==t?void 0:t.creationScope)&&void 0!==e?e:at).importNode(i,!0);wt.currentNode=n;let o=wt.nextNode(),r=0,l=0,a=s[0];for(;void 0!==a;){if(r===a.index){let e;2===a.type?e=new kt(o,o.nextSibling,this,t):1===a.type?e=new a.ctor(o,a.name,a.strings,this,t):6===a.type&&(e=new zt(o,this,t)),this._$AV.push(e),a=s[++l]}r!==(null==a?void 0:a.index)&&(o=wt.nextNode(),r++)}return wt.currentNode=at,n}v(t){let e=0;for(const i of this._$AV)void 0!==i&&(void 0!==i.strings?(i._$AI(t,i,e),e+=i.strings.length-2):i._$AI(t[e])),e++}}class kt{constructor(t,e,i,s){var n;this.type=2,this._$AH=bt,this._$AN=void 0,this._$AA=t,this._$AB=e,this._$AM=i,this.options=s,this._$Cp=null===(n=null==s?void 0:s.isConnected)||void 0===n||n}get _$AU(){var t,e;return null!==(e=null===(t=this._$AM)||void 0===t?void 0:t._$AU)&&void 0!==e?e:this._$Cp}get parentNode(){let t=this._$AA.parentNode;const e=this._$AM;return void 0!==e&&11===(null==t?void 0:t.nodeType)&&(t=e.parentNode),t}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(t,e=this){t=Nt(this,t,e),dt(t)?t===bt||null==t||""===t?(this._$AH!==bt&&this._$AR(),this._$AH=bt):t!==this._$AH&&t!==At&&this._(t):void 0!==t._$litType$?this.g(t):void 0!==t.nodeType?this.$(t):(t=>ct(t)||"function"==typeof(null==t?void 0:t[Symbol.iterator]))(t)?this.T(t):this._(t)}k(t){return this._$AA.parentNode.insertBefore(t,this._$AB)}$(t){this._$AH!==t&&(this._$AR(),this._$AH=this.k(t))}_(t){this._$AH!==bt&&dt(this._$AH)?this._$AA.nextSibling.data=t:this.$(at.createTextNode(t)),this._$AH=t}g(t){var e;const{values:i,_$litType$:s}=t,n="number"==typeof s?this._$AC(t):(void 0===s.el&&(s.el=Et.createElement(Ct(s.h,s.h[0]),this.options)),s);if((null===(e=this._$AH)||void 0===e?void 0:e._$AD)===n)this._$AH.v(i);else{const t=new Rt(n,this),e=t.u(this.options);t.v(i),this.$(e),this._$AH=t}}_$AC(t){let e=xt.get(t.strings);return void 0===e&&xt.set(t.strings,e=new Et(t)),e}T(t){ct(this._$AH)||(this._$AH=[],this._$AR());const e=this._$AH;let i,s=0;for(const n of t)s===e.length?e.push(i=new kt(this.k(ht()),this.k(ht()),this,this.options)):i=e[s],i._$AI(n),s++;s<e.length&&(this._$AR(i&&i._$AB.nextSibling,s),e.length=s)}_$AR(t=this._$AA.nextSibling,e){var i;for(null===(i=this._$AP)||void 0===i||i.call(this,!1,!0,e);t&&t!==this._$AB;){const e=t.nextSibling;t.remove(),t=e}}setConnected(t){var e;void 0===this._$AM&&(this._$Cp=t,null===(e=this._$AP)||void 0===e||e.call(this,t))}}class Ht{constructor(t,e,i,s,n){this.type=1,this._$AH=bt,this._$AN=void 0,this.element=t,this.name=e,this._$AM=s,this.options=n,i.length>2||""!==i[0]||""!==i[1]?(this._$AH=Array(i.length-1).fill(new String),this.strings=i):this._$AH=bt}get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}_$AI(t,e=this,i,s){const n=this.strings;let o=!1;if(void 0===n)t=Nt(this,t,e,0),o=!dt(t)||t!==this._$AH&&t!==At,o&&(this._$AH=t);else{const s=t;let r,l;for(t=n[0],r=0;r<n.length-1;r++)l=Nt(this,s[i+r],e,r),l===At&&(l=this._$AH[r]),o||(o=!dt(l)||l!==this._$AH[r]),l===bt?t=bt:t!==bt&&(t+=(null!=l?l:"")+n[r+1]),this._$AH[r]=l}o&&!s&&this.j(t)}j(t){t===bt?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,null!=t?t:"")}}class Tt extends Ht{constructor(){super(...arguments),this.type=3}j(t){this.element[this.name]=t===bt?void 0:t}}const Ut=it?it.emptyScript:"";class Pt extends Ht{constructor(){super(...arguments),this.type=4}j(t){t&&t!==bt?this.element.setAttribute(this.name,Ut):this.element.removeAttribute(this.name)}}class Ot extends Ht{constructor(t,e,i,s,n){super(t,e,i,s,n),this.type=5}_$AI(t,e=this){var i;if((t=null!==(i=Nt(this,t,e,0))&&void 0!==i?i:bt)===At)return;const s=this._$AH,n=t===bt&&s!==bt||t.capture!==s.capture||t.once!==s.once||t.passive!==s.passive,o=t!==bt&&(s===bt||n);n&&this.element.removeEventListener(this.name,this,s),o&&this.element.addEventListener(this.name,this,t),this._$AH=t}handleEvent(t){var e,i;"function"==typeof this._$AH?this._$AH.call(null!==(i=null===(e=this.options)||void 0===e?void 0:e.host)&&void 0!==i?i:this.element,t):this._$AH.handleEvent(t)}}class zt{constructor(t,e,i){this.element=t,this.type=6,this._$AN=void 0,this._$AM=e,this.options=i}get _$AU(){return this._$AM._$AU}_$AI(t){Nt(this,t)}}const Mt=et.litHtmlPolyfillSupport;null==Mt||Mt(Et,kt),(null!==(tt=et.litHtmlVersions)&&void 0!==tt?tt:et.litHtmlVersions=[]).push("2.8.0");
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */
var It,jt;class Dt extends ${constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){var t,e;const i=super.createRenderRoot();return null!==(t=(e=this.renderOptions).renderBefore)&&void 0!==t||(e.renderBefore=i.firstChild),i}update(t){const e=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(t),this._$Do=((t,e,i)=>{var s,n;const o=null!==(s=null==i?void 0:i.renderBefore)&&void 0!==s?s:e;let r=o._$litPart$;if(void 0===r){const t=null!==(n=null==i?void 0:i.renderBefore)&&void 0!==n?n:null;o._$litPart$=r=new kt(e.insertBefore(ht(),t),t,void 0,null!=i?i:{})}return r._$AI(t),r})(e,this.renderRoot,this.renderOptions)}connectedCallback(){var t;super.connectedCallback(),null===(t=this._$Do)||void 0===t||t.setConnected(!0)}disconnectedCallback(){var t;super.disconnectedCallback(),null===(t=this._$Do)||void 0===t||t.setConnected(!1)}render(){return At}}Dt.finalized=!0,Dt._$litElement$=!0,null===(It=globalThis.litElementHydrateSupport)||void 0===It||It.call(globalThis,{LitElement:Dt});const Wt=globalThis.litElementPolyfillSupport;null==Wt||Wt({LitElement:Dt}),(null!==(jt=globalThis.litElementVersions)&&void 0!==jt?jt:globalThis.litElementVersions=[]).push("3.3.3");
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */
const Lt=t=>e=>"function"==typeof e?((t,e)=>(customElements.define(t,e),e))(t,e):((t,e)=>{const{kind:i,elements:s}=e;return{kind:i,elements:s,finisher(e){customElements.define(t,e)}}})(t,e),Bt=(t,e)=>"method"===e.kind&&e.descriptor&&!("value"in e.descriptor)?{...e,finisher(i){i.createProperty(e.key,t)}}:{kind:"field",key:Symbol(),placement:"own",descriptor:{},originalKey:e.key,initializer(){"function"==typeof e.initializer&&(this[e.key]=e.initializer.call(this))},finisher(i){i.createProperty(e.key,t)}};
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */function Vt(t){return(e,i)=>void 0!==i?((t,e,i)=>{e.constructor.createProperty(i,t)})(t,e,i):Bt(t,e)}
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */function Zt(t){return Vt({...t,state:!0})}
/**
 * @license
 * Copyright 2021 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */var Ft;null===(Ft=window.HTMLSlotElement)||void 0===Ft||Ft.prototype.assignedElements;var qt=r`
  .card {
    padding: 12px;
  }

  .topline {
    display: flex;
    justify-content: space-between;
    gap: 12px;
    align-items: baseline;
  }

  .viewer {
    margin-top: 10px;
    border-radius: 16px;
    overflow: hidden;
    background: rgba(0, 0, 0, 0.04);
    position: relative;

    /* Zoom/pan: evita gesti default del browser */
    touch-action: none;
    overscroll-behavior: contain;
  }

  .zoom-img {
    width: 100%;
    height: auto;
    display: block;
    object-fit: cover;

    transform-origin: 0 0;
    user-select: none;
    -webkit-user-drag: none;
    cursor: grab;
  }

  .zoom-img.dragging {
    cursor: grabbing;
  }

  .controls {
    display: flex;
    gap: 8px;
    align-items: center;
    justify-content: space-between;

    margin-top: 10px;
    border: 1px solid var(--divider-color);
    padding: 2%;
    border-radius: var(--ha-card-border-radius, 12px);

    user-select: none;
    -webkit-tap-highlight-color: transparent;
  }

  .btnrow {
    display: flex;
    gap: 8px;
    align-items: center;
  }

  button {
    border: 0;
    border-radius: 12px;
    padding: 10px 12px;
    cursor: pointer;
  }

  button:disabled {
    opacity: 0.5;
    cursor: default;
  }

  .meta {
    margin-top: 10px;
    font-size: 14px;
    line-height: 1.35;
    opacity: 0.95;

    border: 1px solid var(--divider-color);
    padding: 2%;
    border-radius: var(--ha-card-border-radius, 12px);
  }

  .chips {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-top: 6px;
  }

  .chip {
    padding: 4px 8px;
    border-radius: 999px;
    background: rgba(0, 0, 0, 0.06);
    font-size: 13px;
  }

  .muted {
    opacity: 0.7;
  }

  .error {
    color: var(--error-color, #db4437);
    margin-top: 8px;
    font-size: 13px;
  }
`;const Yt="aws-face-recognition-card",Kt="aws-face-recognition-editor";let Xt=class extends Dt{constructor(){super(...arguments),this._config={}}setConfig(t){this._config=Object.assign({},t)}_valueOrDefault(t,e){return null==t?e:t}_emitConfigChanged(t){this._config=t,this.dispatchEvent(new CustomEvent("config-changed",{detail:{config:t},bubbles:!0,composed:!0}))}_onTextChange(t){var e,i;const s=t.target,n=null===(e=null==s?void 0:s.dataset)||void 0===e?void 0:e.key;if(!n)return;const o=String(null!==(i=s.value)&&void 0!==i?i:"").trim(),r=Object.assign({},this._config);""===o?delete r[n]:r[n]=o,this._emitConfigChanged(r)}_onNumberChange(t){var e,i;const s=t.target,n=null===(e=null==s?void 0:s.dataset)||void 0===e?void 0:e.key;if(!n)return;const o=String(null!==(i=s.value)&&void 0!==i?i:"").trim(),r=Object.assign({},this._config);if(""===o)return delete r[n],void this._emitConfigChanged(r);const l=Number(o);Number.isNaN(l)||(r[n]=l,this._emitConfigChanged(r))}_onSwitchChange(t){var e;const i=t.target,s=null===(e=null==i?void 0:i.dataset)||void 0===e?void 0:e.key;if(!s)return;const n=!!i.checked,o=Object.assign(Object.assign({},this._config),{[s]:n});this._emitConfigChanged(o)}_onCheckboxChange(t){this._onSwitchChange(t)}render(){const t=this._valueOrDefault(this._config.index_url,"/local/snapshots/recognition_index.json"),e=this._valueOrDefault(this._config.image_base_url,"/local/snapshots"),i=this._valueOrDefault(this._config.refresh_seconds,5),s=this._valueOrDefault(this._config.autoplay,!1),n=this._valueOrDefault(this._config.autoplay_seconds,3),o=this._valueOrDefault(this._config.show_object_list,!1);return yt`
      <div class="container">
        <div class="section-title">Sources</div>

        <ha-textfield
          label="Index URL"
          .value=${t}
          data-key="index_url"
          @change=${this._onTextChange}
        ></ha-textfield>

        <ha-textfield
          label="Image base URL"
          .value=${e}
          data-key="image_base_url"
          @change=${this._onTextChange}
        ></ha-textfield>

        <div class="section-title">Refresh</div>

        <ha-textfield
          label="Refresh seconds"
          type="number"
          inputmode="numeric"
          min="0"
          .value=${String(i)}
          data-key="refresh_seconds"
          @change=${this._onNumberChange}
        ></ha-textfield>

        <div class="section-title">Playback</div>

        <ha-formfield label="Autoplay">
          <ha-switch
            .checked=${s}
            data-key="autoplay"
            @change=${this._onSwitchChange}
          ></ha-switch>
        </ha-formfield>

        <ha-textfield
          label="Autoplay seconds"
          type="number"
          inputmode="numeric"
          min="1"
          .value=${String(n)}
          data-key="autoplay_seconds"
          ?disabled=${!s}
          @change=${this._onNumberChange}
        ></ha-textfield>

        <div class="section-title">Display</div>

        <<ha-formfield label="Show object list">
          <ha-switch
            .checked=${o}
            data-key="show_object_list"
            @change=${this._onSwitchChange}
          ></ha-switch>
        </ha-formfield>
      </div>
    `}static get styles(){return r`
      .container {
        display: flex;
        flex-direction: column;
        gap: 14px;
        padding: 8px 2px;
      }

      .section-title {
        font-size: 12px;
        font-weight: 600;
        opacity: 0.8;
        margin-top: 6px;
      }

      ha-textfield {
        width: 100%;
      }

      ha-formfield {
        --mdc-theme-text-primary-on-background: var(--primary-text-color);
      }
    `}};t([Vt({attribute:!1})],Xt.prototype,"hass",void 0),t([Zt()],Xt.prototype,"_config",void 0),Xt=t([Lt(Kt)],Xt);console.info("%c  AWS Face Recognition Card  \n%c  version: v@AWS Face Recognition Card@  ","color: orange; font-weight: bold; background: black","color: white; font-weight: bold; background: dimgray"),window.customCards=window.customCards||[],window.customCards.push({type:Yt,name:"AWS Face Recognition Card",preview:!0,description:"AWS face recognition custom card (WebSocket live + history)"});const Jt="/local/snapshots";let Gt=class extends Dt{constructor(){super(...arguments),this._hasHass=!1,this._hasConfig=!1,this._initDone=!1,this._items=[],this._index=0,this._lastResult=null,this._error=null,this._loading=!1,this._autoplayTimer=null,this._scale=1,this._tx=0,this._ty=0,this._dragging=!1,this._lastTapTime=0,this._doubleTapDelay=300,this._pointers=new Map,this._start={scale:1,tx:0,ty:0},this._pinchStartDist=0,this._pinchCenter={x:0,y:0},this._unsubUpdates=null,this._wsReady=!1,this._reloadPromise=null,this._reloadPending=!1,this._toggleAutoplay=()=>{const t=!this._config.autoplay;this._config=Object.assign(Object.assign({},this._config),{autoplay:t}),this._stopAutoplay(),this._startAutoplay()},this._prev=()=>{this._items.length&&(this._resetZoom(),this._index=(this._index-1+this._items.length)%this._items.length,this._preloadNeighborImages())},this._next=()=>{this._items.length&&(this._resetZoom(),this._index=(this._index+1)%this._items.length,this._preloadNeighborImages())},this._resetZoom=()=>{this._scale=1,this._tx=0,this._ty=0},this._onWheel=t=>{t.preventDefault();const e=t.currentTarget.getBoundingClientRect(),i=t.clientX-e.left,s=t.clientY-e.top,n=this._scale,o=t.deltaY>0?.9:1.1,r=this._clamp(n*o,1,6);this._tx=i-(i-this._tx)*(r/n),this._ty=s-(s-this._ty)*(r/n),this._scale=r,this._applyBounds()},this._onPointerDown=t=>{if("touch"===t.pointerType){const t=Date.now(),e=t-this._lastTapTime;if(this._lastTapTime=t,e>0&&e<this._doubleTapDelay)return void(this._scale>1?this._resetZoom():this._zoom2xAtCenter())}if(t.currentTarget.setPointerCapture(t.pointerId),this._pointers.set(t.pointerId,{x:t.clientX,y:t.clientY}),this._start={scale:this._scale,tx:this._tx,ty:this._ty},1===this._pointers.size&&(this._dragging=!0),2===this._pointers.size){const t=Array.from(this._pointers.values()),e=t[0].x-t[1].x,i=t[0].y-t[1].y;this._pinchStartDist=Math.hypot(e,i),this._pinchCenter={x:(t[0].x+t[1].x)/2,y:(t[0].y+t[1].y)/2}}},this._onPointerMove=t=>{var e;const i=this._pointers.get(t.pointerId);if(!i)return;const s={x:t.clientX,y:t.clientY};if(this._pointers.set(t.pointerId,s),1===this._pointers.size){if(this._scale<=1)return;return this._tx+=s.x-i.x,this._ty+=s.y-i.y,void this._applyBounds()}if(2===this._pointers.size){const t=null===(e=this.shadowRoot)||void 0===e?void 0:e.querySelector(".viewer");if(!t)return;const i=t.getBoundingClientRect(),s=Array.from(this._pointers.values()),n=s[0].x-s[1].x,o=s[0].y-s[1].y,r=Math.hypot(n,o),l=r/(this._pinchStartDist||r),a=this._clamp(this._start.scale*l,1,6),h=this._pinchCenter.x-i.left,d=this._pinchCenter.y-i.top,c=this._scale;this._tx=h-(h-this._tx)*(a/c),this._ty=d-(d-this._ty)*(a/c),this._scale=a,this._applyBounds()}},this._onPointerUp=t=>{this._pointers.delete(t.pointerId),0===this._pointers.size&&(this._dragging=!1)},this._onDblClick=()=>{this._resetZoom()}}set hass(t){this._hass=t,this._hasHass=!0,this._tryInit()}get hass(){return this._hass}static get styles(){return qt}static getConfigElement(){return document.createElement(Kt)}setConfig(t){(t.index_url||t.image_base_url||t.refresh_seconds)&&console.warn("aws-face-recognition-card: index_url, image_base_url, refresh_seconds sono obsoleti (ignorati). La card ora usa WebSocket live + storico."),this._config=Object.assign({autoplay:!1,autoplay_seconds:3,show_object_list:!1},t),this._hasConfig=!0,this._stopAutoplay(),this._startAutoplay(),this._tryInit()}connectedCallback(){super.connectedCallback()}disconnectedCallback(){super.disconnectedCallback(),this._stopAutoplay(),this._cleanupWs()}_tryInit(){var t;this._initDone||this._hasConfig&&this._hasHass&&(null===(t=this.hass)||void 0===t?void 0:t.connection)&&(this._initDone=!0,this._initWsAndLoad())}_isItalian(){var t,e;const i=((null===(e=null===(t=this.hass)||void 0===t?void 0:t.locale)||void 0===e?void 0:e.language)||"").toLowerCase();return"it"===i||i.startsWith("it-")}_t(t){var e,i;const s={title:"Recognition",updated:"updated",time:"Time",unrecognized:"Unrecognized",recognized:"Recognized",objects:"Objects",none:"none",no_image:"No image available",reset_zoom:"Reset zoom",error:"Error loading recognition data"};return null!==(i=null!==(e=(this._isItalian()?{title:"Riconoscimento",updated:"aggiornato",time:"Ora",unrecognized:"Non riconosciuti",recognized:"Riconosciuti",objects:"Oggetti",none:"nessuno",no_image:"Nessuna immagine disponibile",reset_zoom:"Reset zoom",error:"Errore caricamento dati riconoscimento"}:s)[t])&&void 0!==e?e:s[t])&&void 0!==i?i:t}_formatTimestamp(t){if(!t)return"";const e=new Date(t);if(Number.isNaN(e.getTime()))return t;const i=this._isItalian()?"it-IT":"en-US";return new Intl.DateTimeFormat(i,{dateStyle:"short",timeStyle:"medium"}).format(e)}_startAutoplay(){var t,e,i;const s=!!(null===(t=this._config)||void 0===t?void 0:t.autoplay),n=Number(null!==(i=null===(e=this._config)||void 0===e?void 0:e.autoplay_seconds)&&void 0!==i?i:3);!s||n<=0||(this._autoplayTimer=window.setInterval(()=>this._next(),1e3*n))}_stopAutoplay(){this._autoplayTimer&&window.clearInterval(this._autoplayTimer),this._autoplayTimer=null}async _initWsAndLoad(){var t;try{this._wsReady=!0,await this._loadFromWs(),await this._subscribeUpdates()}catch(e){this._error=`${this._t("error")}: ${null!==(t=null==e?void 0:e.message)&&void 0!==t?t:e}`}}_cleanupWs(){var t;try{null===(t=this._unsubUpdates)||void 0===t||t.call(this)}catch(t){}this._unsubUpdates=null,this._wsReady=!1}async _wsSend(t){var e;if(!(null===(e=this.hass)||void 0===e?void 0:e.connection))throw new Error("No hass.connection");return await this.hass.connection.sendMessagePromise(t)}async _loadFromWs(){this._reloadPromise?this._reloadPending=!0:(this._loading=!0,this._reloadPromise=(async()=>{var t;try{const t=await this._wsSend({type:"amazon_face_recognition/get_index",limit:50}),e=Array.isArray(t.items)?t.items:[];e.sort((t,e)=>(e.timestamp||"").localeCompare(t.timestamp||"")),this._items=e,this._updatedAt=t.updated_at,this._error=null;const i=await this._wsSend({type:"amazon_face_recognition/get_last_result"});this._lastResult=i||null;const s=null==i?void 0:i.file;if(s&&e.length){const t=e.findIndex(t=>t.file===s);this._index=t>=0?t:0}else{const t=Math.max(0,e.length-1);this._index=Math.min(this._index,t)}this._preloadNeighborImages()}catch(e){this._error=`${this._t("error")}: ${null!==(t=null==e?void 0:e.message)&&void 0!==t?t:e}`}finally{this._loading=!1}})(),await this._reloadPromise,this._reloadPromise=null,this._reloadPending&&(this._reloadPending=!1,await this._loadFromWs()))}async _subscribeUpdates(){this._unsubUpdates||(this._unsubUpdates=await this.hass.connection.subscribeMessage(t=>{var e;const i=null!==(e=null==t?void 0:t.last_result)&&void 0!==e?e:null,s=null==t?void 0:t.updated_at;s&&(this._updatedAt=s),i&&(this._lastResult=i),(async()=>{await this._loadFromWs(),this._resetZoom()})()},{type:"amazon_face_recognition/subscribe_updates"}))}_preloadNeighborImages(){if(!this._items.length)return;const t=(this._index+1)%this._items.length,e=(this._index-1+this._items.length)%this._items.length,i=t=>{var e;const i=this._items[t],s=null==i?void 0:i.file;if(!s)return;const n=encodeURIComponent(null!==(e=null==i?void 0:i.timestamp)&&void 0!==e?e:s);(new Image).src=`${Jt}/${encodeURIComponent(s)}?v=${n}`};i(t),i(e)}_clamp(t,e,i){return Math.max(e,Math.min(i,t))}_applyBounds(){const t=2e3;this._tx=this._clamp(this._tx,-2e3,t),this._ty=this._clamp(this._ty,-2e3,t)}_zoom2xAtCenter(){var t;const e=null===(t=this.shadowRoot)||void 0===t?void 0:t.querySelector(".viewer");if(!e)return;const i=e.getBoundingClientRect(),s=i.width/2,n=i.height/2,o=this._scale;this._tx=s-(s-this._tx)*(2/o),this._ty=n-(n-this._ty)*(2/o),this._scale=2,this._applyBounds()}getCardSize(){return 3}_buildImageUrl(t){var e,i,s;if(null==t?void 0:t.file){const i=encodeURIComponent(null!==(e=t.timestamp)&&void 0!==e?e:t.file);return`${Jt}/${encodeURIComponent(t.file)}?v=${i}`}const n=(null===(i=this._lastResult)||void 0===i?void 0:i.image_url)||(null===(s=this._lastResult)||void 0===s?void 0:s.latest_url)||"";if(!n)return"";const o=n.includes("?")?"&":"?";return`${n}${o}v=${Date.now()}`}render(){var t,e,i,s,n,o,r,l,a,h,d,c;const u=this._items.length,p=u?this._items[this._index]:null,_=this._buildImageUrl(p),v=null!==(i=null!==(t=null==p?void 0:p.recognized)&&void 0!==t?t:null===(e=this._lastResult)||void 0===e?void 0:e.recognized)&&void 0!==i?i:[],g=null!==(o=null!==(s=null==p?void 0:p.unrecognized_count)&&void 0!==s?s:null===(n=this._lastResult)||void 0===n?void 0:n.unrecognized_count)&&void 0!==o?o:0,$=!!(null===(r=this._config)||void 0===r?void 0:r.show_object_list),m=null!==(h=null!==(l=null==p?void 0:p.objects)&&void 0!==l?l:null===(a=this._lastResult)||void 0===a?void 0:a.objects)&&void 0!==h?h:{},f=Object.entries(m).filter(([,t])=>"number"==typeof t&&t>0).sort((t,e)=>e[1]-t[1]);return yt`
      <ha-card>
        <div class="card">
          <div class="topline">
            <div>
              <b>${this._t("title")}</b>
              <span class="muted">${u?`• ${this._index+1}/${u}`:""}</span>
            </div>
            <div class="muted" style="font-size: 12px;">
              ${this._updatedAt?`${this._t("updated")}: ${this._formatTimestamp(this._updatedAt)}`:""}
            </div>
          </div>

          <div
            class="viewer"
            @wheel=${this._onWheel}
            @pointerdown=${this._onPointerDown}
            @pointermove=${this._onPointerMove}
            @pointerup=${this._onPointerUp}
            @pointercancel=${this._onPointerUp}
            @dblclick=${this._onDblClick}
            style="margin-top:10px;"
          >
            ${_?yt`
                  <img
                    class="zoom-img ${this._dragging?"dragging":""}"
                    src="${_}"
                    alt="snapshot"
                    style="transform: translate(${this._tx}px, ${this._ty}px) scale(${this._scale});"
                  />
                `:yt`<div class="muted" style="padding:16px;">${this._t("no_image")}</div>`}
          </div>

          <div class="controls">
            <div class="btnrow">
              <button @click=${this._prev} ?disabled=${!u}>←</button>
              <button @click=${this._next} ?disabled=${!u}>→</button>
            </div>

            ${this._scale>1?yt`<button @click=${this._resetZoom}>${this._t("reset_zoom")}</button>`:""}

            <div class="btnrow">
              <button @click=${()=>this._loadFromWs()} ?disabled=${this._loading||!this._wsReady}>
                ${this._loading?"…":"↻"}
              </button>
              <button @click=${this._toggleAutoplay} ?disabled=${!u}>
                ${(null===(d=this._config)||void 0===d?void 0:d.autoplay)?"⏸":"▶"}
              </button>
            </div>
          </div>

          ${p||this._lastResult?yt`
                <div class="meta">
                  <div>
                    <span class="muted">${this._t("time")}:</span>
                    ${this._formatTimestamp((null==p?void 0:p.timestamp)||(null===(c=this._lastResult)||void 0===c?void 0:c.timestamp))}
                  </div>

                  <div>
                    <span class="muted">${this._t("unrecognized")}:</span>
                    ${g}
                  </div>

                  <div style="margin-top: 6px;">
                    <span class="muted">${this._t("recognized")}:</span>
                    ${v.length?yt`<div class="chips">
                          ${v.map(t=>yt`<span class="chip">${t}</span>`)}
                        </div>`:yt` <span class="muted">${this._t("none")}</span>`}
                  </div>

                  ${$?yt`
                        <div style="margin-top: 10px;">
                          <span class="muted">${this._t("objects")}:</span>
                          ${f.length?yt`<div class="chips">
                                ${f.map(([t,e])=>yt`<span class="chip">${t} ×${e}</span>`)}
                              </div>`:yt` <span class="muted">${this._t("none")}</span>`}
                        </div>
                      `:""}
                </div>
              `:""}

          ${this._error?yt`<div class="error">${this._error}</div>`:""}
        </div>
      </ha-card>
    `}};t([Vt({attribute:!1})],Gt.prototype,"_config",void 0),t([Vt({attribute:!1})],Gt.prototype,"hass",null),t([Zt()],Gt.prototype,"_items",void 0),t([Zt()],Gt.prototype,"_updatedAt",void 0),t([Zt()],Gt.prototype,"_index",void 0),t([Zt()],Gt.prototype,"_lastResult",void 0),t([Zt()],Gt.prototype,"_error",void 0),t([Zt()],Gt.prototype,"_loading",void 0),t([Zt()],Gt.prototype,"_scale",void 0),t([Zt()],Gt.prototype,"_tx",void 0),t([Zt()],Gt.prototype,"_ty",void 0),t([Zt()],Gt.prototype,"_dragging",void 0),Gt=t([Lt(Yt)],Gt);export{Gt as AwsFaceRecognitionCard};
