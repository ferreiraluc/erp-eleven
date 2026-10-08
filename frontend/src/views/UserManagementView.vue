<template>
  <main class="access-page">
    <ModuleHeader :title="$t('access.users')">
      <button class="erp-button erp-button--secondary" :disabled="loading" @click="loadPage">
        {{ $t("common.refresh") }}
      </button>
      <button class="primary erp-button erp-button--primary" @click="edit()">{{ $t("access.addUser") }}</button>
    </ModuleHeader>
    <p v-if="error" class="notice error" role="alert">{{ error }}</p><p v-if="notice" class="notice success" role="status">{{ notice }}</p>
    <section class="access-card"><div v-if="loading" class="empty">{{ $t('common.loading') }}</div><div v-else class="table-wrap"><table><thead><tr><th>{{ $t('access.user') }}</th><th>{{ $t('access.profile') }}</th><th>{{ $t('access.salesAccess') }}</th><th>{{ $t('access.lastLogin') }}</th><th>{{ $t('access.actions') }}</th></tr></thead><tbody><tr v-for="u in users" :key="u.id"><td><strong>{{ u.nome }}</strong><small class="email">{{ u.email }}</small><span v-if="!u.ativo" class="muted">{{ $t('access.inactive') }}</span><span v-if="u.must_change_password" class="badge">{{ $t('access.temporaryPassword') }}</span></td><td>{{ u.role==='ADMIN' ? $t('access.admin') : $t('access.operational') }}</td><td>{{ u.sales_scope==='own' ? $t('access.onlyOwn') : $t('access.allSales') }}<small class="email">{{ u.sales_seller }}</small></td><td>{{ date(u.ultimo_login) }}</td><td><div class="row-actions"><button class="erp-button erp-button--secondary erp-button--sm" @click="edit(u)">{{ $t('common.edit') }}</button><button class="erp-button erp-button--secondary erp-button--sm" v-if="u.id!==auth.user?.id" @click="resetUser=u;temporary='';error=''">{{ $t('access.resetPassword') }}</button></div></td></tr></tbody></table></div></section>
    <p class="muted">{{ $t('access.userRules') }}</p>
    <div v-if="editing" class="overlay erp-dialog-backdrop" @click.self="editing=false"><section v-erp-dialog class="access-card dialog erp-dialog" role="dialog" aria-modal="true" :aria-label="$t('access.users')"><h2 class="erp-dialog__header">{{ editingId ? $t('common.edit') : $t('access.addUser') }}</h2><form class="erp-dialog__form" @submit.prevent="save"><div class="erp-dialog__body"><div class="fields">
      <label>{{ $t('access.name') }}<input v-model="form.nome" required minlength="2" maxlength="100" /></label>
      <label v-if="!editingId">{{ $t('auth.emailLabel') }}<input v-model="email" type="email" autocomplete="off" required /></label>
      <label v-if="!editingId">{{ $t('access.initialPassword') }}<input v-model="temporary" type="password" autocomplete="new-password" minlength="6" maxlength="72" required /></label>
      <label>{{ $t('access.salesAccess') }}<select v-model="form.sales_scope" :disabled="editingId===auth.user?.id"><option value="all">{{ $t('access.allSales') }}</option><option value="own">{{ $t('access.onlyOwn') }}</option></select></label>
      <label>{{ $t('access.vendorLink') }}<select v-model="form.vendedor_id" :required="form.sales_scope==='own'"><option :value="null">{{ $t('access.select') }}</option><option v-for="v in vendors" :key="v.id" :value="v.id">{{ v.nome }}</option></select></label>
      <label>{{ $t('access.sheetSeller') }}<input v-model="form.sales_seller" list="sheet-sellers" :required="form.sales_scope==='own'" maxlength="100" /><datalist id="sheet-sellers"><option v-for="s in sellers" :key="s">{{ s }}</option></datalist></label>
      <label class="check"><input v-model="form.ativo" type="checkbox" :disabled="editingId===auth.user?.id" />{{ $t('access.active') }}</label>
    </div><p class="muted">{{ $t('access.accessRevokeHelp') }}</p><p v-if="error" class="notice error">{{ error }}</p></div><div class="actions erp-dialog__footer"><button class="erp-button erp-button--secondary" type="button" @click="editing=false">{{ $t('common.cancel') }}</button><button class="primary erp-button erp-button--primary" :disabled="saving">{{ $t('common.save') }}</button></div></form></section></div>
    <div v-if="resetUser" class="overlay erp-dialog-backdrop" @click.self="resetUser=null"><section v-erp-dialog class="access-card dialog erp-dialog" role="dialog" aria-modal="true" :aria-label="$t('access.resetPassword')"><h2 class="erp-dialog__header">{{ $t('access.resetPassword') }} · {{ resetUser.nome }}</h2><form @submit.prevent="reset" class="erp-dialog__form"><div class="erp-dialog__body"><p>{{ $t('access.resetDescription') }}</p><label>{{ $t('access.initialPassword') }}<input v-model="temporary" type="password" autocomplete="new-password" minlength="6" maxlength="72" required /></label><p v-if="error" class="notice error">{{ error }}</p></div><div class="actions erp-dialog__footer"><button class="erp-button erp-button--secondary" type="button" @click="resetUser=null">{{ $t('common.cancel') }}</button><button class="primary erp-button erp-button--primary" :disabled="saving">{{ $t('common.save') }}</button></div></form></section></div>
  </main>
</template>
<script setup lang="ts">
import { vErpDialog } from '@/directives/erpDialog'
import ModuleHeader from '@/components/ModuleHeader.vue'
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { accessAPI, type UserAccess } from '@/services/access'
import { vendorsAPI, type User, type VendorResponse } from '@/services/api'
import { salesBi } from '@/services/salesBi'
import { useAuthStore } from '@/stores/auth'
const auth=useAuthStore(), {t,locale}=useI18n()
const users=ref<User[]>([]),vendors=ref<VendorResponse[]>([]),sellers=ref<string[]>([])
const loading=ref(true),saving=ref(false),editing=ref(false),editingId=ref(''),email=ref(''),temporary=ref(''),error=ref(''),notice=ref(''),resetUser=ref<User|null>(null)
const form=ref<UserAccess>({nome:'',ativo:true,sales_scope:'own',sales_seller:null,vendedor_id:null})
const date=(value?:string)=>value?new Date(value).toLocaleString(locale.value):'—'
async function load(){users.value=await accessAPI.users()}
async function loadPage(){
  loading.value=true;error.value=''
  const [u,v,b]=await Promise.allSettled([accessAPI.users(),vendorsAPI.getAll(),salesBi.overview({})])
  if(u.status==='fulfilled')users.value=u.value
  if(v.status==='fulfilled')vendors.value=v.value
  if(b.status==='fulfilled')sellers.value=b.value.sellers
  if(u.status==='rejected'||v.status==='rejected'||b.status==='rejected')error.value=t('access.connectionError')
  loading.value=false
}
function edit(u?:User){error.value='';notice.value='';editingId.value=u?.id||'';email.value='';temporary.value='';form.value={nome:u?.nome||'',ativo:u?.ativo??true,sales_scope:u?.sales_scope||'own',sales_seller:u?.sales_seller||null,vendedor_id:u?.vendedor_id||null};editing.value=true}
async function save(){saving.value=true;error.value='';try{if(editingId.value)await accessAPI.update(editingId.value,form.value);else await accessAPI.create({...form.value,email:email.value,password:temporary.value});editing.value=false;temporary.value='';await load();notice.value=t('access.saved')}catch{error.value=t('access.userSaveError')}finally{saving.value=false}}
async function reset(){if(!resetUser.value)return;saving.value=true;error.value='';try{await accessAPI.reset(resetUser.value.id,temporary.value);resetUser.value=null;temporary.value='';await load();notice.value=t('access.saved')}catch{error.value=t('access.userSaveError')}finally{saving.value=false}}
onMounted(loadPage)
</script>
<style scoped src="@/components/access/access.css"></style>
<style scoped>.email{display:block;margin:5px 0}.row-actions{display:flex;gap:8px;white-space:nowrap}</style>
