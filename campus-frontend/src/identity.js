// Campus identities are presentation profiles, not backend permissions.
export const IDENTITIES = Object.freeze({
  learner: {label:'学习者', english:'STUDIER', color:'#d2e7ff', trim:'#8aaec9', ink:'#23425e', logo:'logo-dark.png'},
  tutor: {label:'教导者', english:'TUTOR', color:'#e99560', trim:'#ab5a31', ink:'#42240f', logo:'logo-dark.png'},
  builder: {label:'共建者', english:'CO-BUILDER', color:'#171717', trim:'#555b63', ink:'#ffffff', logo:'logo-light.png'}
});
export const identityFor = role => IDENTITIES[role] || IDENTITIES.learner;
export const normalizeRole = role => Object.hasOwn(IDENTITIES,role) ? role : 'learner';
export function paintIdentity(element,role){
 const identity=identityFor(role);element.dataset.identity=normalizeRole(role);
 element.style.setProperty('--role-color',identity.color);
 element.style.setProperty('--role-trim',identity.trim);
 element.style.setProperty('--role-ink',identity.ink);
 return identity;
}
