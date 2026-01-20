function t(t,e,i,s){var o,n=arguments.length,r=n<3?e:null===s?s=Object.getOwnPropertyDescriptor(e,i):s;if("object"==typeof Reflect&&"function"==typeof Reflect.decorate)r=Reflect.decorate(t,e,i,s);else for(var a=t.length-1;a>=0;a--)(o=t[a])&&(r=(n<3?o(r):n>3?o(e,i,r):o(e,i))||r);return n>3&&r&&Object.defineProperty(e,i,r),r}"function"==typeof SuppressedError&&SuppressedError;
/**
 * @license
 * Copyright 2019 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */
const e=window,i=e.ShadowRoot&&(void 0===e.ShadyCSS||e.ShadyCSS.nativeShadow)&&"adoptedStyleSheets"in Document.prototype&&"replace"in CSSStyleSheet.prototype,s=Symbol(),o=new WeakMap;class n{constructor(t,e,i){if(this._$cssResult$=!0,i!==s)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=t,this.t=e}get styleSheet(){let t=this.o;const e=this.t;if(i&&void 0===t){const i=void 0!==e&&1===e.length;i&&(t=o.get(e)),void 0===t&&((this.o=t=new CSSStyleSheet).replaceSync(this.cssText),i&&o.set(e,t))}return t}toString(){return this.cssText}}const r=(t,...e)=>{const i=1===t.length?t[0]:e.reduce((e,i,s)=>e+(t=>{if(!0===t._$cssResult$)return t.cssText;if("number"==typeof t)return t;throw Error("Value passed to 'css' function must be a 'css' function result: "+t+". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.")})(i)+t[s+1],t[0]);return new n(i,t,s)},a=i?t=>t:t=>t instanceof CSSStyleSheet?(t=>{let e="";for(const i of t.cssRules)e+=i.cssText;return(t=>new n("string"==typeof t?t:t+"",void 0,s))(e)})(t):t;
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */var l;const d=window,c=d.trustedTypes,h=c?c.emptyScript:"",p=d.reactiveElementPolyfillSupport,u={toAttribute(t,e){switch(e){case Boolean:t=t?h:null;break;case Object:case Array:t=null==t?t:JSON.stringify(t)}return t},fromAttribute(t,e){let i=t;switch(e){case Boolean:i=null!==t;break;case Number:i=null===t?null:Number(t);break;case Object:case Array:try{i=JSON.parse(t)}catch(t){i=null}}return i}},_=(t,e)=>e!==t&&(e==e||t==t),g={attribute:!0,type:String,converter:u,reflect:!1,hasChanged:_},v="finalized";class m extends HTMLElement{constructor(){super(),this._$Ei=new Map,this.isUpdatePending=!1,this.hasUpdated=!1,this._$El=null,this._$Eu()}static addInitializer(t){var e;this.finalize(),(null!==(e=this.h)&&void 0!==e?e:this.h=[]).push(t)}static get observedAttributes(){this.finalize();const t=[];return this.elementProperties.forEach((e,i)=>{const s=this._$Ep(i,e);void 0!==s&&(this._$Ev.set(s,i),t.push(s))}),t}static createProperty(t,e=g){if(e.state&&(e.attribute=!1),this.finalize(),this.elementProperties.set(t,e),!e.noAccessor&&!this.prototype.hasOwnProperty(t)){const i="symbol"==typeof t?Symbol():"__"+t,s=this.getPropertyDescriptor(t,i,e);void 0!==s&&Object.defineProperty(this.prototype,t,s)}}static getPropertyDescriptor(t,e,i){return{get(){return this[e]},set(s){const o=this[t];this[e]=s,this.requestUpdate(t,o,i)},configurable:!0,enumerable:!0}}static getPropertyOptions(t){return this.elementProperties.get(t)||g}static finalize(){if(this.hasOwnProperty(v))return!1;this[v]=!0;const t=Object.getPrototypeOf(this);if(t.finalize(),void 0!==t.h&&(this.h=[...t.h]),this.elementProperties=new Map(t.elementProperties),this._$Ev=new Map,this.hasOwnProperty("properties")){const t=this.properties,e=[...Object.getOwnPropertyNames(t),...Object.getOwnPropertySymbols(t)];for(const i of e)this.createProperty(i,t[i])}return this.elementStyles=this.finalizeStyles(this.styles),!0}static finalizeStyles(t){const e=[];if(Array.isArray(t)){const i=new Set(t.flat(1/0).reverse());for(const t of i)e.unshift(a(t))}else void 0!==t&&e.push(a(t));return e}static _$Ep(t,e){const i=e.attribute;return!1===i?void 0:"string"==typeof i?i:"string"==typeof t?t.toLowerCase():void 0}_$Eu(){var t;this._$E_=new Promise(t=>this.enableUpdating=t),this._$AL=new Map,this._$Eg(),this.requestUpdate(),null===(t=this.constructor.h)||void 0===t||t.forEach(t=>t(this))}addController(t){var e,i;(null!==(e=this._$ES)&&void 0!==e?e:this._$ES=[]).push(t),void 0!==this.renderRoot&&this.isConnected&&(null===(i=t.hostConnected)||void 0===i||i.call(t))}removeController(t){var e;null===(e=this._$ES)||void 0===e||e.splice(this._$ES.indexOf(t)>>>0,1)}_$Eg(){this.constructor.elementProperties.forEach((t,e)=>{this.hasOwnProperty(e)&&(this._$Ei.set(e,this[e]),delete this[e])})}createRenderRoot(){var t;const s=null!==(t=this.shadowRoot)&&void 0!==t?t:this.attachShadow(this.constructor.shadowRootOptions);return((t,s)=>{i?t.adoptedStyleSheets=s.map(t=>t instanceof CSSStyleSheet?t:t.styleSheet):s.forEach(i=>{const s=document.createElement("style"),o=e.litNonce;void 0!==o&&s.setAttribute("nonce",o),s.textContent=i.cssText,t.appendChild(s)})})(s,this.constructor.elementStyles),s}connectedCallback(){var t;void 0===this.renderRoot&&(this.renderRoot=this.createRenderRoot()),this.enableUpdating(!0),null===(t=this._$ES)||void 0===t||t.forEach(t=>{var e;return null===(e=t.hostConnected)||void 0===e?void 0:e.call(t)})}enableUpdating(t){}disconnectedCallback(){var t;null===(t=this._$ES)||void 0===t||t.forEach(t=>{var e;return null===(e=t.hostDisconnected)||void 0===e?void 0:e.call(t)})}attributeChangedCallback(t,e,i){this._$AK(t,i)}_$EO(t,e,i=g){var s;const o=this.constructor._$Ep(t,i);if(void 0!==o&&!0===i.reflect){const n=(void 0!==(null===(s=i.converter)||void 0===s?void 0:s.toAttribute)?i.converter:u).toAttribute(e,i.type);this._$El=t,null==n?this.removeAttribute(o):this.setAttribute(o,n),this._$El=null}}_$AK(t,e){var i;const s=this.constructor,o=s._$Ev.get(t);if(void 0!==o&&this._$El!==o){const t=s.getPropertyOptions(o),n="function"==typeof t.converter?{fromAttribute:t.converter}:void 0!==(null===(i=t.converter)||void 0===i?void 0:i.fromAttribute)?t.converter:u;this._$El=o,this[o]=n.fromAttribute(e,t.type),this._$El=null}}requestUpdate(t,e,i){let s=!0;void 0!==t&&(((i=i||this.constructor.getPropertyOptions(t)).hasChanged||_)(this[t],e)?(this._$AL.has(t)||this._$AL.set(t,e),!0===i.reflect&&this._$El!==t&&(void 0===this._$EC&&(this._$EC=new Map),this._$EC.set(t,i))):s=!1),!this.isUpdatePending&&s&&(this._$E_=this._$Ej())}async _$Ej(){this.isUpdatePending=!0;try{await this._$E_}catch(t){Promise.reject(t)}const t=this.scheduleUpdate();return null!=t&&await t,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){var t;if(!this.isUpdatePending)return;this.hasUpdated,this._$Ei&&(this._$Ei.forEach((t,e)=>this[e]=t),this._$Ei=void 0);let e=!1;const i=this._$AL;try{e=this.shouldUpdate(i),e?(this.willUpdate(i),null===(t=this._$ES)||void 0===t||t.forEach(t=>{var e;return null===(e=t.hostUpdate)||void 0===e?void 0:e.call(t)}),this.update(i)):this._$Ek()}catch(t){throw e=!1,this._$Ek(),t}e&&this._$AE(i)}willUpdate(t){}_$AE(t){var e;null===(e=this._$ES)||void 0===e||e.forEach(t=>{var e;return null===(e=t.hostUpdated)||void 0===e?void 0:e.call(t)}),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(t)),this.updated(t)}_$Ek(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$E_}shouldUpdate(t){return!0}update(t){void 0!==this._$EC&&(this._$EC.forEach((t,e)=>this._$EO(e,this[e],t)),this._$EC=void 0),this._$Ek()}updated(t){}firstUpdated(t){}}
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */
var b;m[v]=!0,m.elementProperties=new Map,m.elementStyles=[],m.shadowRootOptions={mode:"open"},null==p||p({ReactiveElement:m}),(null!==(l=d.reactiveElementVersions)&&void 0!==l?l:d.reactiveElementVersions=[]).push("1.6.3");const f=window,y=f.trustedTypes,$=y?y.createPolicy("lit-html",{createHTML:t=>t}):void 0,x="$lit$",w=`lit$${(Math.random()+"").slice(9)}$`,A="?"+w,k=`<${A}>`,S=document,C=()=>S.createComment(""),z=t=>null===t||"object"!=typeof t&&"function"!=typeof t,E=Array.isArray,R="[ \t\n\f\r]",N=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,P=/-->/g,j=/>/g,T=RegExp(`>|${R}(?:([^\\s"'>=/]+)(${R}*=${R}*(?:[^ \t\n\f\r"'\`<>=]|("|')|))|$)`,"g"),H=/'/g,U=/"/g,O=/^(?:script|style|textarea|title)$/i,M=Symbol.for("lit-noChange"),I=Symbol.for("lit-nothing"),L=new WeakMap,D=S.createTreeWalker(S,129,null,!1);function V(t,e){if(!Array.isArray(t)||!t.hasOwnProperty("raw"))throw Error("invalid template strings array");return void 0!==$?$.createHTML(e):e}class B{constructor({strings:t,_$litType$:e},i){let s;this.parts=[];let o=0,n=0;const r=t.length-1,a=this.parts,[l,d]=((t,e)=>{const i=t.length-1,s=[];let o,n=2===e?"<svg>":"",r=N;for(let e=0;e<i;e++){const i=t[e];let a,l,d=-1,c=0;for(;c<i.length&&(r.lastIndex=c,l=r.exec(i),null!==l);)c=r.lastIndex,r===N?"!--"===l[1]?r=P:void 0!==l[1]?r=j:void 0!==l[2]?(O.test(l[2])&&(o=RegExp("</"+l[2],"g")),r=T):void 0!==l[3]&&(r=T):r===T?">"===l[0]?(r=null!=o?o:N,d=-1):void 0===l[1]?d=-2:(d=r.lastIndex-l[2].length,a=l[1],r=void 0===l[3]?T:'"'===l[3]?U:H):r===U||r===H?r=T:r===P||r===j?r=N:(r=T,o=void 0);const h=r===T&&t[e+1].startsWith("/>")?" ":"";n+=r===N?i+k:d>=0?(s.push(a),i.slice(0,d)+x+i.slice(d)+w+h):i+w+(-2===d?(s.push(void 0),e):h)}return[V(t,n+(t[i]||"<?>")+(2===e?"</svg>":"")),s]})(t,e);if(this.el=B.createElement(l,i),D.currentNode=this.el.content,2===e){const t=this.el.content,e=t.firstChild;e.remove(),t.append(...e.childNodes)}for(;null!==(s=D.nextNode())&&a.length<r;){if(1===s.nodeType){if(s.hasAttributes()){const t=[];for(const e of s.getAttributeNames())if(e.endsWith(x)||e.startsWith(w)){const i=d[n++];if(t.push(e),void 0!==i){const t=s.getAttribute(i.toLowerCase()+x).split(w),e=/([.?@])?(.*)/.exec(i);a.push({type:1,index:o,name:e[2],strings:t,ctor:"."===e[1]?Y:"?"===e[1]?G:"@"===e[1]?Q:K})}else a.push({type:6,index:o})}for(const e of t)s.removeAttribute(e)}if(O.test(s.tagName)){const t=s.textContent.split(w),e=t.length-1;if(e>0){s.textContent=y?y.emptyScript:"";for(let i=0;i<e;i++)s.append(t[i],C()),D.nextNode(),a.push({type:2,index:++o});s.append(t[e],C())}}}else if(8===s.nodeType)if(s.data===A)a.push({type:2,index:o});else{let t=-1;for(;-1!==(t=s.data.indexOf(w,t+1));)a.push({type:7,index:o}),t+=w.length-1}o++}}static createElement(t,e){const i=S.createElement("template");return i.innerHTML=t,i}}function W(t,e,i=t,s){var o,n,r,a;if(e===M)return e;let l=void 0!==s?null===(o=i._$Co)||void 0===o?void 0:o[s]:i._$Cl;const d=z(e)?void 0:e._$litDirective$;return(null==l?void 0:l.constructor)!==d&&(null===(n=null==l?void 0:l._$AO)||void 0===n||n.call(l,!1),void 0===d?l=void 0:(l=new d(t),l._$AT(t,i,s)),void 0!==s?(null!==(r=(a=i)._$Co)&&void 0!==r?r:a._$Co=[])[s]=l:i._$Cl=l),void 0!==l&&(e=W(t,l._$AS(t,e.values),l,s)),e}class Z{constructor(t,e){this._$AV=[],this._$AN=void 0,this._$AD=t,this._$AM=e}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(t){var e;const{el:{content:i},parts:s}=this._$AD,o=(null!==(e=null==t?void 0:t.creationScope)&&void 0!==e?e:S).importNode(i,!0);D.currentNode=o;let n=D.nextNode(),r=0,a=0,l=s[0];for(;void 0!==l;){if(r===l.index){let e;2===l.type?e=new F(n,n.nextSibling,this,t):1===l.type?e=new l.ctor(n,l.name,l.strings,this,t):6===l.type&&(e=new X(n,this,t)),this._$AV.push(e),l=s[++a]}r!==(null==l?void 0:l.index)&&(n=D.nextNode(),r++)}return D.currentNode=S,o}v(t){let e=0;for(const i of this._$AV)void 0!==i&&(void 0!==i.strings?(i._$AI(t,i,e),e+=i.strings.length-2):i._$AI(t[e])),e++}}class F{constructor(t,e,i,s){var o;this.type=2,this._$AH=I,this._$AN=void 0,this._$AA=t,this._$AB=e,this._$AM=i,this.options=s,this._$Cp=null===(o=null==s?void 0:s.isConnected)||void 0===o||o}get _$AU(){var t,e;return null!==(e=null===(t=this._$AM)||void 0===t?void 0:t._$AU)&&void 0!==e?e:this._$Cp}get parentNode(){let t=this._$AA.parentNode;const e=this._$AM;return void 0!==e&&11===(null==t?void 0:t.nodeType)&&(t=e.parentNode),t}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(t,e=this){t=W(this,t,e),z(t)?t===I||null==t||""===t?(this._$AH!==I&&this._$AR(),this._$AH=I):t!==this._$AH&&t!==M&&this._(t):void 0!==t._$litType$?this.g(t):void 0!==t.nodeType?this.$(t):(t=>E(t)||"function"==typeof(null==t?void 0:t[Symbol.iterator]))(t)?this.T(t):this._(t)}k(t){return this._$AA.parentNode.insertBefore(t,this._$AB)}$(t){this._$AH!==t&&(this._$AR(),this._$AH=this.k(t))}_(t){this._$AH!==I&&z(this._$AH)?this._$AA.nextSibling.data=t:this.$(S.createTextNode(t)),this._$AH=t}g(t){var e;const{values:i,_$litType$:s}=t,o="number"==typeof s?this._$AC(t):(void 0===s.el&&(s.el=B.createElement(V(s.h,s.h[0]),this.options)),s);if((null===(e=this._$AH)||void 0===e?void 0:e._$AD)===o)this._$AH.v(i);else{const t=new Z(o,this),e=t.u(this.options);t.v(i),this.$(e),this._$AH=t}}_$AC(t){let e=L.get(t.strings);return void 0===e&&L.set(t.strings,e=new B(t)),e}T(t){E(this._$AH)||(this._$AH=[],this._$AR());const e=this._$AH;let i,s=0;for(const o of t)s===e.length?e.push(i=new F(this.k(C()),this.k(C()),this,this.options)):i=e[s],i._$AI(o),s++;s<e.length&&(this._$AR(i&&i._$AB.nextSibling,s),e.length=s)}_$AR(t=this._$AA.nextSibling,e){var i;for(null===(i=this._$AP)||void 0===i||i.call(this,!1,!0,e);t&&t!==this._$AB;){const e=t.nextSibling;t.remove(),t=e}}setConnected(t){var e;void 0===this._$AM&&(this._$Cp=t,null===(e=this._$AP)||void 0===e||e.call(this,t))}}class K{constructor(t,e,i,s,o){this.type=1,this._$AH=I,this._$AN=void 0,this.element=t,this.name=e,this._$AM=s,this.options=o,i.length>2||""!==i[0]||""!==i[1]?(this._$AH=Array(i.length-1).fill(new String),this.strings=i):this._$AH=I}get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}_$AI(t,e=this,i,s){const o=this.strings;let n=!1;if(void 0===o)t=W(this,t,e,0),n=!z(t)||t!==this._$AH&&t!==M,n&&(this._$AH=t);else{const s=t;let r,a;for(t=o[0],r=0;r<o.length-1;r++)a=W(this,s[i+r],e,r),a===M&&(a=this._$AH[r]),n||(n=!z(a)||a!==this._$AH[r]),a===I?t=I:t!==I&&(t+=(null!=a?a:"")+o[r+1]),this._$AH[r]=a}n&&!s&&this.j(t)}j(t){t===I?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,null!=t?t:"")}}class Y extends K{constructor(){super(...arguments),this.type=3}j(t){this.element[this.name]=t===I?void 0:t}}const q=y?y.emptyScript:"";class G extends K{constructor(){super(...arguments),this.type=4}j(t){t&&t!==I?this.element.setAttribute(this.name,q):this.element.removeAttribute(this.name)}}class Q extends K{constructor(t,e,i,s,o){super(t,e,i,s,o),this.type=5}_$AI(t,e=this){var i;if((t=null!==(i=W(this,t,e,0))&&void 0!==i?i:I)===M)return;const s=this._$AH,o=t===I&&s!==I||t.capture!==s.capture||t.once!==s.once||t.passive!==s.passive,n=t!==I&&(s===I||o);o&&this.element.removeEventListener(this.name,this,s),n&&this.element.addEventListener(this.name,this,t),this._$AH=t}handleEvent(t){var e,i;"function"==typeof this._$AH?this._$AH.call(null!==(i=null===(e=this.options)||void 0===e?void 0:e.host)&&void 0!==i?i:this.element,t):this._$AH.handleEvent(t)}}class X{constructor(t,e,i){this.element=t,this.type=6,this._$AN=void 0,this._$AM=e,this.options=i}get _$AU(){return this._$AM._$AU}_$AI(t){W(this,t)}}const J=f.litHtmlPolyfillSupport;
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */
var tt;null==J||J(B,F),(null!==(b=f.litHtmlVersions)&&void 0!==b?b:f.litHtmlVersions=[]).push("2.8.0");const et=window,it=et.trustedTypes,st=it?it.createPolicy("lit-html",{createHTML:t=>t}):void 0,ot="$lit$",nt=`lit$${(Math.random()+"").slice(9)}$`,rt="?"+nt,at=`<${rt}>`,lt=document,dt=()=>lt.createComment(""),ct=t=>null===t||"object"!=typeof t&&"function"!=typeof t,ht=Array.isArray,pt="[ \t\n\f\r]",ut=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,_t=/-->/g,gt=/>/g,vt=RegExp(`>|${pt}(?:([^\\s"'>=/]+)(${pt}*=${pt}*(?:[^ \t\n\f\r"'\`<>=]|("|')|))|$)`,"g"),mt=/'/g,bt=/"/g,ft=/^(?:script|style|textarea|title)$/i,yt=(t=>(e,...i)=>({_$litType$:t,strings:e,values:i}))(1),$t=Symbol.for("lit-noChange"),xt=Symbol.for("lit-nothing"),wt=new WeakMap,At=lt.createTreeWalker(lt,129,null,!1);function kt(t,e){if(!Array.isArray(t)||!t.hasOwnProperty("raw"))throw Error("invalid template strings array");return void 0!==st?st.createHTML(e):e}const St=(t,e)=>{const i=t.length-1,s=[];let o,n=2===e?"<svg>":"",r=ut;for(let e=0;e<i;e++){const i=t[e];let a,l,d=-1,c=0;for(;c<i.length&&(r.lastIndex=c,l=r.exec(i),null!==l);)c=r.lastIndex,r===ut?"!--"===l[1]?r=_t:void 0!==l[1]?r=gt:void 0!==l[2]?(ft.test(l[2])&&(o=RegExp("</"+l[2],"g")),r=vt):void 0!==l[3]&&(r=vt):r===vt?">"===l[0]?(r=null!=o?o:ut,d=-1):void 0===l[1]?d=-2:(d=r.lastIndex-l[2].length,a=l[1],r=void 0===l[3]?vt:'"'===l[3]?bt:mt):r===bt||r===mt?r=vt:r===_t||r===gt?r=ut:(r=vt,o=void 0);const h=r===vt&&t[e+1].startsWith("/>")?" ":"";n+=r===ut?i+at:d>=0?(s.push(a),i.slice(0,d)+ot+i.slice(d)+nt+h):i+nt+(-2===d?(s.push(void 0),e):h)}return[kt(t,n+(t[i]||"<?>")+(2===e?"</svg>":"")),s]};class Ct{constructor({strings:t,_$litType$:e},i){let s;this.parts=[];let o=0,n=0;const r=t.length-1,a=this.parts,[l,d]=St(t,e);if(this.el=Ct.createElement(l,i),At.currentNode=this.el.content,2===e){const t=this.el.content,e=t.firstChild;e.remove(),t.append(...e.childNodes)}for(;null!==(s=At.nextNode())&&a.length<r;){if(1===s.nodeType){if(s.hasAttributes()){const t=[];for(const e of s.getAttributeNames())if(e.endsWith(ot)||e.startsWith(nt)){const i=d[n++];if(t.push(e),void 0!==i){const t=s.getAttribute(i.toLowerCase()+ot).split(nt),e=/([.?@])?(.*)/.exec(i);a.push({type:1,index:o,name:e[2],strings:t,ctor:"."===e[1]?Pt:"?"===e[1]?Tt:"@"===e[1]?Ht:Nt})}else a.push({type:6,index:o})}for(const e of t)s.removeAttribute(e)}if(ft.test(s.tagName)){const t=s.textContent.split(nt),e=t.length-1;if(e>0){s.textContent=it?it.emptyScript:"";for(let i=0;i<e;i++)s.append(t[i],dt()),At.nextNode(),a.push({type:2,index:++o});s.append(t[e],dt())}}}else if(8===s.nodeType)if(s.data===rt)a.push({type:2,index:o});else{let t=-1;for(;-1!==(t=s.data.indexOf(nt,t+1));)a.push({type:7,index:o}),t+=nt.length-1}o++}}static createElement(t,e){const i=lt.createElement("template");return i.innerHTML=t,i}}function zt(t,e,i=t,s){var o,n,r,a;if(e===$t)return e;let l=void 0!==s?null===(o=i._$Co)||void 0===o?void 0:o[s]:i._$Cl;const d=ct(e)?void 0:e._$litDirective$;return(null==l?void 0:l.constructor)!==d&&(null===(n=null==l?void 0:l._$AO)||void 0===n||n.call(l,!1),void 0===d?l=void 0:(l=new d(t),l._$AT(t,i,s)),void 0!==s?(null!==(r=(a=i)._$Co)&&void 0!==r?r:a._$Co=[])[s]=l:i._$Cl=l),void 0!==l&&(e=zt(t,l._$AS(t,e.values),l,s)),e}class Et{constructor(t,e){this._$AV=[],this._$AN=void 0,this._$AD=t,this._$AM=e}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(t){var e;const{el:{content:i},parts:s}=this._$AD,o=(null!==(e=null==t?void 0:t.creationScope)&&void 0!==e?e:lt).importNode(i,!0);At.currentNode=o;let n=At.nextNode(),r=0,a=0,l=s[0];for(;void 0!==l;){if(r===l.index){let e;2===l.type?e=new Rt(n,n.nextSibling,this,t):1===l.type?e=new l.ctor(n,l.name,l.strings,this,t):6===l.type&&(e=new Ut(n,this,t)),this._$AV.push(e),l=s[++a]}r!==(null==l?void 0:l.index)&&(n=At.nextNode(),r++)}return At.currentNode=lt,o}v(t){let e=0;for(const i of this._$AV)void 0!==i&&(void 0!==i.strings?(i._$AI(t,i,e),e+=i.strings.length-2):i._$AI(t[e])),e++}}class Rt{constructor(t,e,i,s){var o;this.type=2,this._$AH=xt,this._$AN=void 0,this._$AA=t,this._$AB=e,this._$AM=i,this.options=s,this._$Cp=null===(o=null==s?void 0:s.isConnected)||void 0===o||o}get _$AU(){var t,e;return null!==(e=null===(t=this._$AM)||void 0===t?void 0:t._$AU)&&void 0!==e?e:this._$Cp}get parentNode(){let t=this._$AA.parentNode;const e=this._$AM;return void 0!==e&&11===(null==t?void 0:t.nodeType)&&(t=e.parentNode),t}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(t,e=this){t=zt(this,t,e),ct(t)?t===xt||null==t||""===t?(this._$AH!==xt&&this._$AR(),this._$AH=xt):t!==this._$AH&&t!==$t&&this._(t):void 0!==t._$litType$?this.g(t):void 0!==t.nodeType?this.$(t):(t=>ht(t)||"function"==typeof(null==t?void 0:t[Symbol.iterator]))(t)?this.T(t):this._(t)}k(t){return this._$AA.parentNode.insertBefore(t,this._$AB)}$(t){this._$AH!==t&&(this._$AR(),this._$AH=this.k(t))}_(t){this._$AH!==xt&&ct(this._$AH)?this._$AA.nextSibling.data=t:this.$(lt.createTextNode(t)),this._$AH=t}g(t){var e;const{values:i,_$litType$:s}=t,o="number"==typeof s?this._$AC(t):(void 0===s.el&&(s.el=Ct.createElement(kt(s.h,s.h[0]),this.options)),s);if((null===(e=this._$AH)||void 0===e?void 0:e._$AD)===o)this._$AH.v(i);else{const t=new Et(o,this),e=t.u(this.options);t.v(i),this.$(e),this._$AH=t}}_$AC(t){let e=wt.get(t.strings);return void 0===e&&wt.set(t.strings,e=new Ct(t)),e}T(t){ht(this._$AH)||(this._$AH=[],this._$AR());const e=this._$AH;let i,s=0;for(const o of t)s===e.length?e.push(i=new Rt(this.k(dt()),this.k(dt()),this,this.options)):i=e[s],i._$AI(o),s++;s<e.length&&(this._$AR(i&&i._$AB.nextSibling,s),e.length=s)}_$AR(t=this._$AA.nextSibling,e){var i;for(null===(i=this._$AP)||void 0===i||i.call(this,!1,!0,e);t&&t!==this._$AB;){const e=t.nextSibling;t.remove(),t=e}}setConnected(t){var e;void 0===this._$AM&&(this._$Cp=t,null===(e=this._$AP)||void 0===e||e.call(this,t))}}class Nt{constructor(t,e,i,s,o){this.type=1,this._$AH=xt,this._$AN=void 0,this.element=t,this.name=e,this._$AM=s,this.options=o,i.length>2||""!==i[0]||""!==i[1]?(this._$AH=Array(i.length-1).fill(new String),this.strings=i):this._$AH=xt}get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}_$AI(t,e=this,i,s){const o=this.strings;let n=!1;if(void 0===o)t=zt(this,t,e,0),n=!ct(t)||t!==this._$AH&&t!==$t,n&&(this._$AH=t);else{const s=t;let r,a;for(t=o[0],r=0;r<o.length-1;r++)a=zt(this,s[i+r],e,r),a===$t&&(a=this._$AH[r]),n||(n=!ct(a)||a!==this._$AH[r]),a===xt?t=xt:t!==xt&&(t+=(null!=a?a:"")+o[r+1]),this._$AH[r]=a}n&&!s&&this.j(t)}j(t){t===xt?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,null!=t?t:"")}}class Pt extends Nt{constructor(){super(...arguments),this.type=3}j(t){this.element[this.name]=t===xt?void 0:t}}const jt=it?it.emptyScript:"";class Tt extends Nt{constructor(){super(...arguments),this.type=4}j(t){t&&t!==xt?this.element.setAttribute(this.name,jt):this.element.removeAttribute(this.name)}}class Ht extends Nt{constructor(t,e,i,s,o){super(t,e,i,s,o),this.type=5}_$AI(t,e=this){var i;if((t=null!==(i=zt(this,t,e,0))&&void 0!==i?i:xt)===$t)return;const s=this._$AH,o=t===xt&&s!==xt||t.capture!==s.capture||t.once!==s.once||t.passive!==s.passive,n=t!==xt&&(s===xt||o);o&&this.element.removeEventListener(this.name,this,s),n&&this.element.addEventListener(this.name,this,t),this._$AH=t}handleEvent(t){var e,i;"function"==typeof this._$AH?this._$AH.call(null!==(i=null===(e=this.options)||void 0===e?void 0:e.host)&&void 0!==i?i:this.element,t):this._$AH.handleEvent(t)}}class Ut{constructor(t,e,i){this.element=t,this.type=6,this._$AN=void 0,this._$AM=e,this.options=i}get _$AU(){return this._$AM._$AU}_$AI(t){zt(this,t)}}const Ot=et.litHtmlPolyfillSupport;null==Ot||Ot(Ct,Rt),(null!==(tt=et.litHtmlVersions)&&void 0!==tt?tt:et.litHtmlVersions=[]).push("2.8.0");
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */
var Mt,It;class Lt extends m{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){var t,e;const i=super.createRenderRoot();return null!==(t=(e=this.renderOptions).renderBefore)&&void 0!==t||(e.renderBefore=i.firstChild),i}update(t){const e=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(t),this._$Do=((t,e,i)=>{var s,o;const n=null!==(s=null==i?void 0:i.renderBefore)&&void 0!==s?s:e;let r=n._$litPart$;if(void 0===r){const t=null!==(o=null==i?void 0:i.renderBefore)&&void 0!==o?o:null;n._$litPart$=r=new Rt(e.insertBefore(dt(),t),t,void 0,null!=i?i:{})}return r._$AI(t),r})(e,this.renderRoot,this.renderOptions)}connectedCallback(){var t;super.connectedCallback(),null===(t=this._$Do)||void 0===t||t.setConnected(!0)}disconnectedCallback(){var t;super.disconnectedCallback(),null===(t=this._$Do)||void 0===t||t.setConnected(!1)}render(){return $t}}Lt.finalized=!0,Lt._$litElement$=!0,null===(Mt=globalThis.litElementHydrateSupport)||void 0===Mt||Mt.call(globalThis,{LitElement:Lt});const Dt=globalThis.litElementPolyfillSupport;null==Dt||Dt({LitElement:Lt}),(null!==(It=globalThis.litElementVersions)&&void 0!==It?It:globalThis.litElementVersions=[]).push("3.3.3");
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */
const Vt=(t,e)=>"method"===e.kind&&e.descriptor&&!("value"in e.descriptor)?{...e,finisher(i){i.createProperty(e.key,t)}}:{kind:"field",key:Symbol(),placement:"own",descriptor:{},originalKey:e.key,initializer(){"function"==typeof e.initializer&&(this[e.key]=e.initializer.call(this))},finisher(i){i.createProperty(e.key,t)}};
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */function Bt(t){return(e,i)=>void 0!==i?((t,e,i)=>{e.constructor.createProperty(i,t)})(t,e,i):Vt(t,e)}
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */function Wt(t){return Bt({...t,state:!0})}
/**
 * @license
 * Copyright 2021 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */var Zt;null===(Zt=window.HTMLSlotElement)||void 0===Zt||Zt.prototype.assignedElements;var Ft=r`
  .card {
    padding: 12px;
  }

  .afr-tabs {
  display: flex;
  gap: 8px;
  padding: 10px 12px;
  margin-bottom: 8px;
}

  .afr-tab {
    min-width: 90px;
    text-align: center;

  }


  .afr-tab {
    border: 1px solid rgba(127,127,127,0.35);
    background: rgba(0,0,0,0.04);
    border-radius: 999px;
    padding: 7px 12px;
    cursor: pointer;
    font-size: 13px;
  }

  .afr-tab.is-active {
    background: rgba(0,0,0,0.12);
    font-weight: 700;
  }

  .afr-empty {
    padding: 16px 8px;
    text-align: center;
  }

  .afr-divider {
  height: 1px;
  background: rgba(127,127,127,0.25);
  margin: 16px 0;
}

.afr-input {
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid rgba(127,127,127,0.35);
  background: rgba(255,255,255,0.03);
  font-size: 14px;
}

.afr-input:focus {
  outline: none;
  border-color: rgba(0, 120, 255, 0.6);
}

.afr-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
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

  /*
   * Premium toolbar
   * NOTE: the markup still uses ".controls" so we keep this class name.
   */
  .controls {
    --afr-surface: rgba(0, 0, 0, 0.04);
    --afr-surface-2: rgba(0, 0, 0, 0.06);
    --afr-border: rgba(127, 127, 127, 0.22);
    --afr-shadow: 0 10px 26px rgba(0, 0, 0, 0.18);

    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;

    margin-top: 10px;
    padding: 10px;
    border-radius: 18px;
    border: 1px solid var(--afr-border);
    background: var(--afr-surface);
    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.12);

    user-select: none;
    -webkit-tap-highlight-color: transparent;
  }

  /* When HA is in dark mode we need a slightly different surface */
  @media (prefers-color-scheme: dark) {
    .controls {
      --afr-surface: rgba(255, 255, 255, 0.04);
      --afr-surface-2: rgba(255, 255, 255, 0.06);
      --afr-border: rgba(127, 127, 127, 0.26);
    }
  }

  .btnrow {
    display: flex;
    gap: 10px;
    align-items: center;
    flex-wrap: nowrap;
    /* desktop/default: keep LIVE centered between toolgroups */
    flex: 1 1 auto;
    justify-content: center;
    min-width: 0;
  }

  /* Responsive toolbar layout (mobile)
   * - Row 1 (full width): Reset (if visible) + LIVE
   *   - if reset hidden, LIVE becomes full width automatically
   *   - if reset visible, reset keeps a fixed width similar to the navigation group
   * - Row 2: navigation group on the left, actions group on the right
   * NOTE: This changes ONLY positioning; button look/colors stay untouched.
   */
  @media (max-width: 520px) {
    .controls {
      flex-wrap: wrap;
      align-items: stretch;
      justify-content: flex-start;
    }

    /* Row 1 */
    .btnrow.mid {
      order: 1;
      flex: 1 1 100%;
      justify-content: stretch;
    }

    /* Reset button: approximate the width of the nav toolgroup
       (2 icon buttons + gap + toolgroup padding) */
    .btnrow.mid .resetbtn {
      width: calc(44px * 2 + 6px + 6px * 2);
      flex: 0 0 auto;
    }

    /* LIVE takes remaining space */
    .btnrow.mid .livebtn {
      flex: 1 1 auto;
      min-width: 0;
      justify-content: center;
    }

    /* Row 2 */
    .toolgroup.nav {
      order: 2;
      flex: 0 0 auto;
    }

    .toolgroup.actions {
      order: 2;
      flex: 0 0 auto;
      margin-left: auto;
    }
  }

  /* Icon-only reset zoom (appears only when zoomed) */
  .resetbtn {
    /* keep it visually grouped with the toolbar even when it's not inside a .toolgroup */
    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.10);
  }

  .toolgroup {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px;
    border-radius: 999px;
    border: 1px solid var(--afr-border);
    background: var(--afr-surface-2);
  }

  .iconbtn {
    width: 44px;
    height: 44px;
    border-radius: 999px;
    border: 1px solid rgba(127, 127, 127, 0.18);
    background: rgba(0, 0, 0, 0.02);
    color: var(--primary-text-color);
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    transition: transform 120ms ease, box-shadow 120ms ease, background 120ms ease, border-color 120ms ease, opacity 120ms ease;
  }

  @media (prefers-color-scheme: dark) {
    .iconbtn {
      background: rgba(255, 255, 255, 0.03);
      border-color: rgba(127, 127, 127, 0.22);
    }
  }

  .iconbtn:hover {
    background: rgba(0, 0, 0, 0.06);
    box-shadow: 0 6px 14px rgba(0, 0, 0, 0.16);
    transform: translateY(-1px);
  }

  @media (prefers-color-scheme: dark) {
    .iconbtn:hover {
      background: rgba(255, 255, 255, 0.06);
    }
  }

  .iconbtn:active {
    transform: translateY(0);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
  }

  .iconbtn:disabled {
    opacity: 0.45;
    cursor: default;
    box-shadow: none;
    transform: none;
  }

  .pillbtn {
    height: 44px;
    padding: 0 14px;
    border-radius: 999px;
    border: 1px solid var(--afr-border);
    background: rgba(0, 0, 0, 0.02);
    color: var(--primary-text-color);
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 0.2px;
    transition: transform 120ms ease, box-shadow 120ms ease, background 120ms ease;
  }

  @media (prefers-color-scheme: dark) {
    .pillbtn {
      background: rgba(255, 255, 255, 0.03);
    }
  }

  .pillbtn:hover {
    box-shadow: 0 6px 14px rgba(0, 0, 0, 0.14);
    transform: translateY(-1px);
  }

  .pillbtn:active {
    transform: translateY(0);
  }

  .pillbtn:disabled {
    opacity: 0.45;
    cursor: default;
    box-shadow: none;
    transform: none;
  }

  .livebtn {
    border: 0;
    background: color-mix(in srgb, var(--primary-color) 88%, black 12%);
    color: var(--text-primary-color, #fff);
    box-shadow: var(--afr-shadow);
  }

  .livebtn:hover {
    box-shadow: 0 14px 34px rgba(0, 0, 0, 0.22);
  }

  .livebadge {
    width: 8px;
    height: 8px;
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.95);
    box-shadow: 0 0 0 4px rgba(255, 255, 255, 0.22);
  }

  .afr-spin {
    animation: afrSpin 900ms linear infinite;
  }

  @keyframes afrSpin {
    from {
      transform: rotate(0deg);
    }
    to {
      transform: rotate(360deg);
    }
  }

  /*
   * Premium information sections (meta + plates)
   */
  .sectionCard {
    margin-top: 10px;
    padding: 12px;
    border-radius: 16px;
    border: 1px solid rgba(127, 127, 127, 0.22);
    background: rgba(0, 0, 0, 0.02);
  }

  @media (prefers-color-scheme: dark) {
    .sectionCard {
      background: rgba(255, 255, 255, 0.03);
      border-color: rgba(127, 127, 127, 0.26);
    }
  }

  .sectionHead {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    margin-bottom: 10px;
  }

  .sectionTitle {
    font-size: 15px;
    font-weight: 800;
    letter-spacing: 0.2px;
  }

  .sectionHint {
    padding: 4px 10px;
    border-radius: 999px;
    border: 1px solid rgba(127, 127, 127, 0.22);
    background: rgba(0, 0, 0, 0.03);
    font-size: 12px;
    opacity: 0.85;
  }

  @media (prefers-color-scheme: dark) {
    .sectionHint {
      background: rgba(255, 255, 255, 0.05);
      border-color: rgba(127, 127, 127, 0.26);
    }
  }

  .metaGrid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
  }

  @media (max-width: 420px) {
    .metaGrid {
      grid-template-columns: 1fr;
    }
  }

  .kv {
    padding: 10px;
    border-radius: 14px;
    border: 1px solid rgba(127, 127, 127, 0.22);
    background: rgba(0, 0, 0, 0.03);
  }

  @media (prefers-color-scheme: dark) {
    .kv {
      background: rgba(255, 255, 255, 0.04);
      border-color: rgba(127, 127, 127, 0.26);
    }
  }

  .kvLabel {
    font-size: 12px;
    opacity: 0.65;
    margin-bottom: 6px;
  }

  .kvValue {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 14px;
    font-weight: 700;
  }

  .kvValue ha-icon {
    opacity: 0.85;
  }

  .divider {
    height: 1px;
    background: rgba(127, 127, 127, 0.22);
    margin: 12px 0;
  }

  .sectionLine {
    display: grid;
    grid-template-columns: 110px 1fr;
    gap: 10px;
    align-items: start;
  }

  @media (max-width: 420px) {
    .sectionLine {
      grid-template-columns: 1fr;
    }
  }

  .sectionK {
    font-size: 12px;
    opacity: 0.65;
    padding-top: 2px;
  }

  .sectionV {
    min-width: 0;
  }

  .badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 10px;
    border-radius: 999px;
    border: 1px solid rgba(127, 127, 127, 0.22);
    background: rgba(0, 0, 0, 0.03);
    font-size: 12px;
    font-weight: 800;
    letter-spacing: 0.2px;
  }

  @media (prefers-color-scheme: dark) {
    .badge {
      background: rgba(255, 255, 255, 0.05);
      border-color: rgba(127, 127, 127, 0.26);
    }
  }

  .badge.ok {
    color: var(--success-color, #2e7d32);
    border-color: color-mix(in srgb, var(--success-color, #2e7d32) 40%, rgba(127, 127, 127, 0.22));
    background: color-mix(in srgb, var(--success-color, #2e7d32) 12%, transparent);
  }

  .badge.bad {
    color: var(--error-color, #db4437);
    border-color: color-mix(in srgb, var(--error-color, #db4437) 40%, rgba(127, 127, 127, 0.22));
    background: color-mix(in srgb, var(--error-color, #db4437) 12%, transparent);
  }

  .badge.neutral {
    opacity: 0.85;
  }

  .chips {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-top: 6px;
  }

  .chip {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 10px;
    border-radius: 999px;
    border: 1px solid rgba(127, 127, 127, 0.18);
    background: rgba(0, 0, 0, 0.03);
    font-size: 13px;
    font-weight: 650;
  }

  @media (prefers-color-scheme: dark) {
    .chip {
      background: rgba(255, 255, 255, 0.05);
      border-color: rgba(127, 127, 127, 0.26);
    }
  }

  .chip--person ha-icon {
    opacity: 0.85;
  }

  .chip--object {
    font-weight: 600;
  }

  .chipCount {
    margin-left: 4px;
    padding: 2px 6px;
    border-radius: 999px;
    border: 1px solid rgba(127, 127, 127, 0.22);
    background: rgba(0, 0, 0, 0.03);
    font-size: 12px;
    opacity: 0.85;
  }

  @media (prefers-color-scheme: dark) {
    .chipCount {
      background: rgba(255, 255, 255, 0.05);
      border-color: rgba(127, 127, 127, 0.26);
    }
  }

  /* Plates list */
  .platesList {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .plateRow {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 10px;
    border-radius: 14px;
    border: 1px solid rgba(127, 127, 127, 0.22);
    background: rgba(0, 0, 0, 0.03);
  }

  @media (prefers-color-scheme: dark) {
    .plateRow {
      background: rgba(255, 255, 255, 0.04);
      border-color: rgba(127, 127, 127, 0.26);
    }
  }

  .plateLeft {
    display: flex;
    align-items: center;
    gap: 10px;
    min-width: 0;
  }

  .plateIcon {
    width: 34px;
    height: 34px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border-radius: 12px;
    border: 1px solid rgba(127, 127, 127, 0.22);
    background: rgba(0, 0, 0, 0.03);
    flex: 0 0 auto;
  }

  @media (prefers-color-scheme: dark) {
    .plateIcon {
      background: rgba(255, 255, 255, 0.05);
      border-color: rgba(127, 127, 127, 0.26);
    }
  }

  .plateText {
    min-width: 0;
  }

  .plateTitle {
    font-weight: 850;
    letter-spacing: 0.2px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .plateSub {
    margin-top: 2px;
    font-size: 12px;
    opacity: 0.7;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .confBadge {
    padding: 6px 10px;
    border-radius: 999px;
    border: 1px solid rgba(127, 127, 127, 0.22);
    background: rgba(0, 0, 0, 0.03);
    font-size: 12px;
    font-weight: 850;
    letter-spacing: 0.2px;
    flex: 0 0 auto;
  }

  @media (prefers-color-scheme: dark) {
    .confBadge {
      background: rgba(255, 255, 255, 0.05);
      border-color: rgba(127, 127, 127, 0.26);
    }
  }

  .muted {
    opacity: 0.7;
  }

  .error {
    color: var(--error-color, #db4437);
    margin-top: 8px;
    font-size: 13px;
  }
`;const Kt="aws-face-recognition-card",Yt="aws-face-recognition-editor",qt={title:"Recognition",updated:"Updated",time:"Time",unrecognized:"Unrecognized",recognized:"Recognized",objects:"Objects",none:"None",no_image:"No image available",reset_zoom:"Reset zoom",error:"Error",unknown_person_found:"Unknown person found",status_unknown:"Unknown detected",status_clear:"All clear",plates:"Plates",no_camera:"No linked camera",live_to_snapshot:"Back to snapshot",live_view:"View live",prev:"Previous",next:"Next",back:"Back",refresh:"Refresh",play:"Play",pause:"Pause",download:"Download",editor_playback:"Playback",editor_autoplay:"Autoplay",editor_autoplay_seconds:"Autoplay seconds",editor_display:"Display",editor_show_object_list:"Show object list"},Gt={en:qt,it:{title:"Riconoscimento",updated:"Aggiornato",time:"Ora",unrecognized:"Non riconosciuti",recognized:"Riconosciuti",objects:"Oggetti",none:"Nessuno",no_image:"Nessuna immagine disponibile",reset_zoom:"Reimposta zoom",error:"Errore",unknown_person_found:"Sconosciuto rilevato",status_unknown:"Sconosciuto rilevato",status_clear:"Nessuno sconosciuto",plates:"Targhe",no_camera:"Nessuna camera associata",live_to_snapshot:"Torna allo snapshot",live_view:"Visualizza live",prev:"Precedente",next:"Successivo",back:"Indietro",refresh:"Aggiorna",play:"Play",pause:"Pausa",download:"Scarica",editor_playback:"Riproduzione",editor_autoplay:"Riproduzione automatica",editor_autoplay_seconds:"Secondi autoplay",editor_display:"Visualizzazione",editor_show_object_list:"Mostra elenco oggetti"},fr:{title:"Reconnaissance",updated:"Mis à jour",time:"Heure",unrecognized:"Non reconnus",recognized:"Reconnus",objects:"Objets",none:"Aucun",no_image:"Aucune image disponible",reset_zoom:"Réinitialiser le zoom",error:"Erreur",unknown_person_found:"Personne inconnue détectée",status_unknown:"Inconnu détecté",status_clear:"Rien à signaler",plates:"Plaques",no_camera:"Aucune caméra liée",live_to_snapshot:"Retour à l’instantané",live_view:"Voir en direct",prev:"Précédent",next:"Suivant",back:"Retour",refresh:"Rafraîchir",play:"Lecture",pause:"Pause",download:"Télécharger",editor_playback:"Lecture",editor_autoplay:"Lecture automatique",editor_autoplay_seconds:"Secondes d’autoplay",editor_display:"Affichage",editor_show_object_list:"Afficher la liste d’objets"},es:{title:"Reconocimiento",updated:"Actualizado",time:"Hora",unrecognized:"No reconocidos",recognized:"Reconocidos",objects:"Objetos",none:"Ninguno",no_image:"No hay imagen disponible",reset_zoom:"Restablecer zoom",error:"Error",unknown_person_found:"Persona desconocida detectada",status_unknown:"Desconocido detectado",status_clear:"Todo ok",plates:"Matrículas",no_camera:"No hay cámara vinculada",live_to_snapshot:"Volver a la instantánea",live_view:"Ver en vivo",prev:"Anterior",next:"Siguiente",back:"Atrás",refresh:"Actualizar",play:"Reproducir",pause:"Pausa",download:"Descargar",editor_playback:"Reproducción",editor_autoplay:"Reproducción automática",editor_autoplay_seconds:"Segundos de autoplay",editor_display:"Visualización",editor_show_object_list:"Mostrar lista de objetos"},pt:{title:"Reconhecimento",updated:"Atualizado",time:"Hora",unrecognized:"Não reconhecidos",recognized:"Reconhecidos",objects:"Objetos",none:"Nenhum",no_image:"Nenhuma imagem disponível",reset_zoom:"Repor zoom",error:"Erro",unknown_person_found:"Pessoa desconhecida detetada",status_unknown:"Desconhecido detetado",status_clear:"Tudo ok",plates:"Matrículas",no_camera:"Nenhuma câmera associada",live_to_snapshot:"Voltar ao snapshot",live_view:"Ver ao vivo",prev:"Anterior",next:"Seguinte",back:"Voltar",refresh:"Atualizar",play:"Reproduzir",pause:"Pausa",download:"Transferir",editor_playback:"Reprodução",editor_autoplay:"Reprodução automática",editor_autoplay_seconds:"Segundos de autoplay",editor_display:"Visualização",editor_show_object_list:"Mostrar lista de objetos"},pl:{title:"Rozpoznawanie",updated:"Zaktualizowano",time:"Czas",unrecognized:"Nierozpoznani",recognized:"Rozpoznani",objects:"Obiekty",none:"Brak",no_image:"Brak dostępnego obrazu",reset_zoom:"Resetuj powiększenie",error:"Błąd",unknown_person_found:"Wykryto nieznaną osobę",status_unknown:"Wykryto nieznaną",status_clear:"Wszystko OK",plates:"Tablice",no_camera:"Brak powiązanej kamery",live_to_snapshot:"Powrót do migawki",live_view:"Podgląd na żywo",prev:"Poprzednie",next:"Następne",back:"Wstecz",refresh:"Odśwież",play:"Odtwórz",pause:"Pauza",download:"Pobierz",editor_playback:"Odtwarzanie",editor_autoplay:"Autoodtwarzanie",editor_autoplay_seconds:"Sekundy autoodtwarzania",editor_display:"Wyświetlanie",editor_show_object_list:"Pokaż listę obiektów"},de:{title:"Erkennung",updated:"Aktualisiert",time:"Uhrzeit",unrecognized:"Nicht erkannt",recognized:"Erkannt",objects:"Objekte",none:"Keine",no_image:"Kein Bild verfügbar",reset_zoom:"Zoom zurücksetzen",error:"Fehler",unknown_person_found:"Unbekannte Person erkannt",status_unknown:"Unbekannt erkannt",status_clear:"Alles ok",plates:"Kennzeichen",no_camera:"Keine verknüpfte Kamera",live_to_snapshot:"Zurück zum Snapshot",live_view:"Live anzeigen",prev:"Zurück",next:"Weiter",back:"Zurück",refresh:"Aktualisieren",play:"Abspielen",pause:"Pause",download:"Herunterladen",editor_playback:"Wiedergabe",editor_autoplay:"Automatische Wiedergabe",editor_autoplay_seconds:"Autoplay-Sekunden",editor_display:"Anzeige",editor_show_object_list:"Objektliste anzeigen"}};function Qt(t,e,i){var s,o;const n=function(t){var e;const i=String((null==t?void 0:t.language)||(null===(e=null==t?void 0:t.locale)||void 0===e?void 0:e.language)||"").toLowerCase().split("-")[0];return Gt[i]?i:"en"}(t);let r=null!==(o=null!==(s=(Gt[n]||qt)[e])&&void 0!==s?s:qt[e])&&void 0!==o?o:e;if(i)for(const[t,e]of Object.entries(i))r=r.replaceAll(`{${t}}`,String(e));return r}function Xt(t,e){var i;if(!e)return"";const s=new Date(e);if(Number.isNaN(s.getTime()))return e;const o=String((null==t?void 0:t.language)||(null===(i=null==t?void 0:t.locale)||void 0===i?void 0:i.language)||"en")||"en";return new Intl.DateTimeFormat(o,{dateStyle:"short",timeStyle:"medium"}).format(s)}let Jt=class extends Lt{constructor(){super(...arguments),this._config={}}setConfig(t){this._config=Object.assign({},t)}_emitConfigChanged(t){this._config=t,this.dispatchEvent(new CustomEvent("config-changed",{detail:{config:t},bubbles:!0,composed:!0}))}_onSwitchChange(t){var e;const i=t.target,s=null===(e=null==i?void 0:i.dataset)||void 0===e?void 0:e.key;if(!s)return;const o=!!i.checked,n=Object.assign(Object.assign({},this._config),{[s]:o});this._emitConfigChanged(n)}_onNumberChange(t){var e,i;const s=t.target,o=null===(e=null==s?void 0:s.dataset)||void 0===e?void 0:e.key;if(!o)return;const n=String(null!==(i=s.value)&&void 0!==i?i:"").trim();if(!n){const t=Object.assign({},this._config);return delete t[o],void this._emitConfigChanged(t)}const r=Number(n);Number.isNaN(r)||this._emitConfigChanged(Object.assign(Object.assign({},this._config),{[o]:r}))}render(){var t,e,i;const s=null!==(t=this._config.autoplay)&&void 0!==t&&t,o=null!==(e=this._config.autoplay_seconds)&&void 0!==e?e:3,n=null!==(i=this._config.show_object_list)&&void 0!==i&&i;return yt`
      <div class="container">
        <div class="section-title">${Qt(this.hass,"editor_playback")}</div>

        <ha-formfield label=${Qt(this.hass,"editor_autoplay")}>
          <ha-switch
            .checked=${s}
            data-key="autoplay"
            @change=${this._onSwitchChange}
          ></ha-switch>
        </ha-formfield>

        <ha-textfield
          label=${Qt(this.hass,"editor_autoplay_seconds")}
          type="number"
          inputmode="numeric"
          min="1"
          .value=${String(o)}
          data-key="autoplay_seconds"
          ?disabled=${!s}
          @change=${this._onNumberChange}
        ></ha-textfield>

        <div class="section-title">${Qt(this.hass,"editor_display")}</div>

        <ha-formfield label=${Qt(this.hass,"editor_show_object_list")}>
          <ha-switch
            .checked=${n}
            data-key="show_object_list"
            @change=${this._onSwitchChange}
          ></ha-switch>
        </ha-formfield>
        <hr style="width: 100%; color: var(--divider-color); margin-top:60px;" />
        <div class="donations" style="display: flex">
          <a href="https://www.buymeacoffee.com/madmicio" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 60px !important;width: 217px !important;" ></a>
          <form action="https://www.paypal.com/donate" method="post" target="_top">
          <input type="hidden" name="hosted_button_id" value="U5VQ9LHM82B7Q" />
          <input type="image" src="https://pics.paypal.com/00/s/ODdjZjVlZjAtOWVmYS00NjQyLTkyZTUtNWQ3MmMzMmIxYTcx/file.PNG" border="0" name="submit" title="PayPal - The safer, easier way to pay online!" alt="Donate with PayPal button" style="height:60px;" />
          <img alt="" border="0" src="https://www.paypal.com/en_IT/i/scr/pixel.gif" width="1" height="1" />
          </form>

      </div>
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
    `}};t([Bt({attribute:!1})],Jt.prototype,"hass",void 0),t([Wt()],Jt.prototype,"_config",void 0),Jt=t([(t=>e=>"function"==typeof e?((t,e)=>(customElements.define(t,e),e))(t,e):((t,e)=>{const{kind:i,elements:s}=e;return{kind:i,elements:s,finisher(e){customElements.define(t,e)}}})(t,e))(Yt)],Jt);console.info("%c  AWS Face Recognition Card  \n%c  version: v@AWS Face Recognition Card@  ","color: orange; font-weight: bold; background: black","color: white; font-weight: bold; background: dimgray");const te="/local/amazon_face_recognition_scan",ee=["amazon_face_recognition/get_index","amazon_face_recognition/index"],ie=["amazon_face_recognition/get_last_result","amazon_face_recognition/last_result"];class se extends Lt{constructor(){super(...arguments),this._items=[],this._index=0,this._lastResult=null,this._error=null,this._loading=!1,this._scale=1,this._tx=0,this._ty=0,this._dragging=!1,this._scanCarsEnabled=!1,this._live=!1,this._autoplayTimer=null,this._pointers=new Map,this._start={scale:1,tx:0,ty:0},this._pinchStartDist=0,this._pinchCenter={x:0,y:0},this._lastTapTime=0,this._doubleTapDelay=300,this._hasConfig=!1,this._initDone=!1,this._unsubUpdates=null,this._warnedObsolete=!1,this._toggleLive=()=>{this._live=!this._live,this._resetZoom()},this._toggleAutoplay=()=>{const t=!this._config.autoplay;this._config=Object.assign(Object.assign({},this._config),{autoplay:t}),this._stopAutoplay(),this._startAutoplay()},this._prev=()=>{this._items.length&&(this._resetZoom(),this._index=(this._index-1+this._items.length)%this._items.length,this._preloadNeighborImages(),this._live=!1)},this._next=()=>{this._items.length&&(this._resetZoom(),this._index=(this._index+1)%this._items.length,this._preloadNeighborImages(),this._live=!1)},this._resetZoom=()=>{this._scale=1,this._tx=0,this._ty=0},this._onWheel=t=>{t.preventDefault();const e=t.currentTarget.getBoundingClientRect(),i=t.clientX-e.left,s=t.clientY-e.top,o=this._scale,n=t.deltaY>0?.9:1.1,r=this._clamp(o*n,1,6);this._tx=i-(i-this._tx)*(r/o),this._ty=s-(s-this._ty)*(r/o),this._scale=r,this._normalizeAfterZoom(),this._applyBounds()},this._onPointerDown=t=>{if("touch"===t.pointerType){const t=Date.now(),e=t-this._lastTapTime;if(this._lastTapTime=t,e>0&&e<this._doubleTapDelay)return void(this._scale>1?this._resetZoom():this._zoom2xAtCenter())}if(t.currentTarget.setPointerCapture(t.pointerId),this._pointers.set(t.pointerId,{x:t.clientX,y:t.clientY}),this._start={scale:this._scale,tx:this._tx,ty:this._ty},1===this._pointers.size&&(this._dragging=!0),2===this._pointers.size){const t=Array.from(this._pointers.values()),e=t[0].x-t[1].x,i=t[0].y-t[1].y;this._pinchStartDist=Math.hypot(e,i),this._pinchCenter={x:(t[0].x+t[1].x)/2,y:(t[0].y+t[1].y)/2}}},this._onPointerMove=t=>{var e;const i=this._pointers.get(t.pointerId);if(!i)return;const s={x:t.clientX,y:t.clientY};if(this._pointers.set(t.pointerId,s),1===this._pointers.size){if(this._scale<=1)return;return this._tx+=s.x-i.x,this._ty+=s.y-i.y,void this._applyBounds()}if(2===this._pointers.size){const t=null===(e=this.shadowRoot)||void 0===e?void 0:e.querySelector(".viewer");if(!t)return;const i=t.getBoundingClientRect(),s=Array.from(this._pointers.values()),o=s[0].x-s[1].x,n=s[0].y-s[1].y,r=Math.hypot(o,n),a=r/(this._pinchStartDist||r),l=this._clamp(this._start.scale*a,1,6),d=this._pinchCenter.x-i.left,c=this._pinchCenter.y-i.top,h=this._scale;this._tx=d-(d-this._tx)*(l/h),this._ty=c-(c-this._ty)*(l/h),this._scale=l,this._normalizeAfterZoom(),this._applyBounds()}},this._onPointerUp=t=>{this._pointers.delete(t.pointerId),0===this._pointers.size&&(this._dragging=!1)},this._onDblClick=()=>{this._resetZoom()}}set hass(t){this._hass=t,this._tryInit()}get hass(){return this._hass}static get styles(){return Ft}static getConfigElement(){return document.createElement(Yt)}setConfig(t){this._hasConfig=!0,this._config=Object.assign({autoplay:!1,autoplay_seconds:3,show_object_list:!1},t),this._stopAutoplay(),this._startAutoplay(),this._tryInit()}connectedCallback(){super.connectedCallback(),this._tryInit()}disconnectedCallback(){super.disconnectedCallback(),this._stopAutoplay(),this._cleanupWs(),this._initDone=!1}_tryInit(){var t;this._initDone||this._hasConfig&&(null===(t=this._hass)||void 0===t?void 0:t.connection)&&(this._initDone=!0,this._initWsAndLoad())}async _initWsAndLoad(){var t;try{await this._loadFromWs(),await this._subscribeUpdates()}catch(e){this._error=`${Qt(this.hass,"error")}: ${null!==(t=null==e?void 0:e.message)&&void 0!==t?t:e}`}}_cleanupWs(){var t;try{null===(t=this._unsubUpdates)||void 0===t||t.call(this)}catch(t){}this._unsubUpdates=null,this._loading=!1}_downloadCurrent(){var t,e;const i=this._items.length?this._items[this._index]:null,s=null==i?void 0:i.file;let o=s?`${te}/${encodeURIComponent(s)}?v=${s}`:"";if(!o){const i=(null===(t=this._lastResult)||void 0===t?void 0:t.image_url)||(null===(e=this._lastResult)||void 0===e?void 0:e.latest_url)||"";o=i?`${i}${i.includes("?")?"&":"?"}v=${Date.now()}`:""}if(!o)return;const n=document.createElement("a");n.href=o,n.download=s||"recognition.jpg",n.rel="noopener",n.target="_blank",document.body.appendChild(n),n.click(),n.remove()}_startAutoplay(){var t,e,i;if(!(null===(t=this._config)||void 0===t?void 0:t.autoplay))return;const s=Number(null!==(i=null===(e=this._config)||void 0===e?void 0:e.autoplay_seconds)&&void 0!==i?i:3);s>0&&(this._autoplayTimer=window.setInterval(()=>this._next(),1e3*s))}_stopAutoplay(){this._autoplayTimer&&window.clearInterval(this._autoplayTimer),this._autoplayTimer=null}async _wsSend(t){var e;if(!(null===(e=this.hass)||void 0===e?void 0:e.connection))throw new Error("No hass.connection");return await this.hass.connection.sendMessagePromise(t)}async _wsSendFirstOk(t,e){let i=null;for(const s of t)try{return await this._wsSend(Object.assign({type:s},e))}catch(t){i=t}throw null!=i?i:new Error("WebSocket call failed")}async _loadFromWs(){var t;if(!this._loading){this._loading=!0;try{const t=await this._wsSendFirstOk(ee,{limit:100}),e=[...Array.isArray(t.items)?t.items:[]].sort((t,e)=>(e.timestamp||"").localeCompare(t.timestamp||"")),i=await this._wsSendFirstOk(ie,{});this._items=e,this._updatedAt=null==t?void 0:t.updated_at,this._lastResult=i||null,this._scanCarsEnabled=!!(null==i?void 0:i.scan_cars_enabled),this._error=null;const s=null==i?void 0:i.file;if(s&&e.length){const t=e.findIndex(t=>t.file===s);this._index=t>=0?t:0}else this._index=0;this._preloadNeighborImages()}catch(e){this._error=`${Qt(this.hass,"error")}: ${null!==(t=null==e?void 0:e.message)&&void 0!==t?t:e}`}finally{this._loading=!1}}}async _subscribeUpdates(){this._unsubUpdates||(this._unsubUpdates=await this.hass.connection.subscribeMessage(t=>{(null==t?void 0:t.updated_at)&&(this._updatedAt=t.updated_at),(null==t?void 0:t.last_result)&&(this._lastResult=t.last_result),this._loadFromWs(),this._resetZoom()},{type:"amazon_face_recognition/subscribe_updates"}))}_preloadNeighborImages(){if(!this._items.length)return;const t=(this._index+1)%this._items.length,e=(this._index-1+this._items.length)%this._items.length,i=t=>{var e;const i=null===(e=this._items[t])||void 0===e?void 0:e.file;if(!i)return;(new Image).src=`${te}/${encodeURIComponent(i)}?v=${i}`};i(t),i(e)}_clamp(t,e,i){return Math.max(e,Math.min(i,t))}_normalizeAfterZoom(){this._scale<=1.001&&(this._scale=1,this._tx=0,this._ty=0)}_applyBounds(){const t=2e3;this._tx=this._clamp(this._tx,-2e3,t),this._ty=this._clamp(this._ty,-2e3,t)}_zoom2xAtCenter(){var t;const e=null===(t=this.shadowRoot)||void 0===t?void 0:t.querySelector(".viewer");if(!e)return;const i=e.getBoundingClientRect(),s=i.width/2,o=i.height/2,n=this._scale;this._tx=s-(s-this._tx)*(2/n),this._ty=o-(o-this._ty)*(2/n),this._scale=2,this._applyBounds()}getCardSize(){return 3}_imgUrlForItem(t){var e,i;const s=null==t?void 0:t.file;if(s)return`${te}/${encodeURIComponent(s)}?v=${s}`;const o=(null===(e=this._lastResult)||void 0===e?void 0:e.image_url)||(null===(i=this._lastResult)||void 0===i?void 0:i.latest_url)||"";return o?`${o}${o.includes("?")?"&":"?"}v=${Date.now()}`:""}_renderPlatesSection(t){var e,i,s,o,n;const r=null!==(n=null!==(s=null!==(e=null==t?void 0:t.plates)&&void 0!==e?e:null===(i=this._lastResult)||void 0===i?void 0:i.plates)&&void 0!==s?s:null===(o=this._lastResult)||void 0===o?void 0:o.detected_plates)&&void 0!==n?n:[],a=Array.isArray(r)?r:[];return a.length?yt`
      <div class="sectionCard">
        <div class="sectionHead">
          <div class="sectionTitle">${Qt(this.hass,"plates")}</div>
          <div class="sectionHint">${a.length}</div>
        </div>

        <div class="platesList">
          ${a.map(t=>{const e=t.owner?t.owner:t.plate,i=t.owner?t.plate:t.vehicle_label?t.vehicle_label:"",s="number"==typeof t.confidence?Math.round(t.confidence):null;return yt`
              <div class="plateRow">
                <div class="plateLeft">
                  <div class="plateIcon" aria-hidden="true">
                    <ha-icon icon=${t.owner?"mdi:account":"mdi:car"}></ha-icon>
                  </div>

                  <div class="plateText">
                    <div class="plateTitle">${e}</div>
                    ${i?yt`<div class="plateSub">${i}</div>`:yt``}
                  </div>
                </div>

                ${null!==s?yt`<div class="confBadge">${s}%</div>`:yt``}
              </div>
            `})}
        </div>
      </div>
    `:yt``}render(){var t,e,i,s,o,n,r,a,l,d,c,h,p,u,_,g,v,m,b;const f=this._items.length,y=f?this._items[this._index]:null,$=(null==y?void 0:y.camera_entity)||(null===(t=this._lastResult)||void 0===t?void 0:t.camera_entity)||(null===(e=this._lastResult)||void 0===e?void 0:e.entity_id)||"",x=$?this.hass.states[$]:void 0,w=!!x,A=this._imgUrlForItem(y),k=null!==(o=null!==(i=null==y?void 0:y.recognized)&&void 0!==i?i:null===(s=this._lastResult)||void 0===s?void 0:s.recognized)&&void 0!==o?o:[],S=null!==(a=null!==(n=null==y?void 0:y.unknown_person_found)&&void 0!==n?n:null===(r=this._lastResult)||void 0===r?void 0:r.unknown_person_found)&&void 0!==a&&a,C=!!(null===(l=this._config)||void 0===l?void 0:l.show_object_list),z=null!==(h=null!==(d=null==y?void 0:y.objects)&&void 0!==d?d:null===(c=this._lastResult)||void 0===c?void 0:c.objects)&&void 0!==h?h:{},E=Object.entries(z).filter(([,t])=>"number"==typeof t&&t>0).sort((t,e)=>e[1]-t[1]);return null!==(_=null!==(p=null==y?void 0:y.plates)&&void 0!==p?p:null===(u=this._lastResult)||void 0===u?void 0:u.plates)&&void 0!==_?_:null===(g=this._lastResult)||void 0===g?void 0:g.detected_plates,"plates"in(y||{})||"plates"in(this._lastResult||{})||this._lastResult,yt`
      <ha-card>
        <div class="card">
          <div class="topline">
            <div>
              <b>${Qt(this.hass,"title")}</b>
              <span class="muted">${f?`• ${this._index+1}/${f}`:""}</span>
            </div>
            <div class="muted" style="font-size: 12px;">
              ${this._updatedAt?`${Qt(this.hass,"updated")}: ${Xt(this.hass,this._updatedAt)}`:""}
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
            ${this._live?w?yt`
                      <ha-camera-stream
                        .hass=${this.hass}
                        .stateObj=${x}
                      ></ha-camera-stream>
                    `:yt`<div class="muted" style="padding:16px;">${Qt(this.hass,"no_camera")}</div>`:A?yt`
                      <img
                        class="zoom-img ${this._dragging?"dragging":""}"
                        src="${A}"
                        alt="snapshot"
                        style="transform: translate(${this._tx}px, ${this._ty}px) scale(${this._scale});"
                      />
                    `:yt`<div class="muted" style="padding:16px;">${Qt(this.hass,"no_image")}</div>`}

          </div>

          <div class="controls">
            <div class="toolgroup nav" role="group" aria-label="Navigation">
              <button class="iconbtn" @click=${this._prev} ?disabled=${!f} title=${Qt(this.hass,"prev")}>
                <ha-icon icon="mdi:chevron-left"></ha-icon>
              </button>
              <button class="iconbtn" @click=${this._next} ?disabled=${!f} title=${Qt(this.hass,"next")}>
                <ha-icon icon="mdi:chevron-right"></ha-icon>
              </button>
            </div>

            <!-- Center row: reset + LIVE. On mobile this becomes row #1 (full width) -->
            <div class="btnrow mid">
              ${this._scale>1?yt`
                    <!--
                      Reset zoom should never wrap/resize the toolbar.
                      Keep it icon-only (tooltip provides the label).
                    -->
                    <button class="iconbtn resetbtn" @click=${this._resetZoom} title=${Qt(this.hass,"reset_zoom")}>
                      <ha-icon icon="mdi:magnify-minus-outline"></ha-icon>
                    </button>
                  `:""}

              <button
                class="pillbtn livebtn"
                @click=${this._toggleLive}
                ?disabled=${!w&&!this._live}
                title=${this._live?Qt(this.hass,"live_to_snapshot"):Qt(this.hass,"live_view")}
              >
                <span class="livebadge" aria-hidden="true"></span>
                <ha-icon icon=${this._live?"mdi:arrow-left":"mdi:cctv"}></ha-icon>
                <span>${this._live?Qt(this.hass,"back"):"LIVE"}</span>
              </button>
            </div>

            <div class="toolgroup actions" role="group" aria-label="Actions">
              <button
                class="iconbtn"
                @click=${()=>this._loadFromWs()}
                ?disabled=${this._loading}
                title=${Qt(this.hass,"refresh")}
              >
                <ha-icon
                  class=${this._loading?"afr-spin":""}
                  icon=${this._loading?"mdi:loading":"mdi:refresh"}
                ></ha-icon>
              </button>

              <button
                class="iconbtn"
                @click=${this._toggleAutoplay}
                ?disabled=${!f}
                title=${(null===(v=this._config)||void 0===v?void 0:v.autoplay)?Qt(this.hass,"pause"):Qt(this.hass,"play")}
              >
                <ha-icon icon=${(null===(m=this._config)||void 0===m?void 0:m.autoplay)?"mdi:pause":"mdi:play"}></ha-icon>
              </button>

              <button
                class="iconbtn"
                @click=${this._downloadCurrent}
                ?disabled=${!A}
                title=${Qt(this.hass,"download")}
              >
                <ha-icon icon="mdi:download"></ha-icon>
              </button>
            </div>
          </div>

          ${y||this._lastResult?yt`
                <div class="sectionCard">
                  <div class="metaGrid">
                    <div class="kv">
                      <div class="kvLabel">${Qt(this.hass,"time")}</div>
                      <div class="kvValue">
                        <ha-icon icon="mdi:clock-outline"></ha-icon>
                        <span>${Xt(this.hass,(null==y?void 0:y.timestamp)||(null===(b=this._lastResult)||void 0===b?void 0:b.timestamp))}</span>
                      </div>
                    </div>

                    <div class="kv">
                      <div class="kvLabel">${Qt(this.hass,"unknown_person_found")}</div>
                      <div class="kvValue">
                        ${S?yt`<span class="badge bad">
                              <ha-icon icon="mdi:alert-circle"></ha-icon>
                              <span>${Qt(this.hass,"status_unknown")}</span>
                            </span>`:yt`<span class="badge ok">
                              <ha-icon icon="mdi:check-circle"></ha-icon>
                              <span>${Qt(this.hass,"status_clear")}</span>
                            </span>`}
                      </div>
                    </div>
                  </div>

                  <div class="divider"></div>

                  <div class="sectionLine">
                    <div class="sectionK">${Qt(this.hass,"recognized")}</div>
                    <div class="sectionV">
                      ${k.length?yt`<div class="chips">
                            ${k.map(t=>yt`<span class="chip chip--person"><ha-icon icon="mdi:account"></ha-icon>${t}</span>`)}
                          </div>`:yt`<span class="badge neutral"><ha-icon icon="mdi:account-off"></ha-icon>${Qt(this.hass,"none")}</span>`}
                    </div>
                  </div>

                  ${C?yt`
                        <div class="sectionLine" style="margin-top:10px;">
                          <div class="sectionK">${Qt(this.hass,"objects")}</div>
                          <div class="sectionV">
                            ${E.length?yt`<div class="chips">
                                  ${E.map(([t,e])=>yt`<span class="chip chip--object">${t}<span class="chipCount">${e}</span></span>`)}
                                </div>`:yt`<span class="badge neutral"><ha-icon icon="mdi:cube-outline"></ha-icon>${Qt(this.hass,"none")}</span>`}
                          </div>
                        </div>
                      `:""}
                </div>
              `:""}
          ${this._scanCarsEnabled?this._renderPlatesSection(y):""}
          ${this._error?yt`<div class="error">${this._error}</div>`:""}
        </div>
      </ha-card>
    `}}t([Bt({attribute:!1})],se.prototype,"_config",void 0),t([Bt({attribute:!1})],se.prototype,"hass",null),t([Wt()],se.prototype,"_items",void 0),t([Wt()],se.prototype,"_updatedAt",void 0),t([Wt()],se.prototype,"_index",void 0),t([Wt()],se.prototype,"_lastResult",void 0),t([Wt()],se.prototype,"_error",void 0),t([Wt()],se.prototype,"_loading",void 0),t([Wt()],se.prototype,"_scale",void 0),t([Wt()],se.prototype,"_tx",void 0),t([Wt()],se.prototype,"_ty",void 0),t([Wt()],se.prototype,"_dragging",void 0),t([Wt()],se.prototype,"_scanCarsEnabled",void 0),t([Wt()],se.prototype,"_live",void 0),customElements.get(Kt)||customElements.define(Kt,se),window.customCards=window.customCards||[],window.customCards.some(t=>(null==t?void 0:t.type)===Kt)||window.customCards.push({type:Kt,name:"AWS Face Recognition Card",preview:!0,description:"AWS face recognition custom card (WebSocket)"});export{se as AwsFaceRecognitionCard};
