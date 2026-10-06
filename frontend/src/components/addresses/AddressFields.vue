<template>
  <div class="fields">
    <label>{{ tr('País') }}<select :value="modelValue.pais" @change="update('pais',($event.target as HTMLSelectElement).value)"><option value="PY">{{ tr('Paraguai') }}</option><option value="BR">{{ tr('Brasil') }}</option></select></label>
    <label>{{tr(nameLabel || 'Nome do destinatário')}}<input :value="modelValue.nome" @input="update('nome',($event.target as HTMLInputElement).value)" maxlength="120"/></label>
    <label v-for="f in fields" :key="f.key" :class="{wide:f.key==='endereco'}">{{tr(f.key==='cpf' && modelValue.pais==='PY' ? 'RUC/C.I (opcional na impressão)' : f.label)}}
      <input :value="modelValue[f.key]" @input="update(f.key,($event.target as HTMLInputElement).value)" @blur="onBlur(f.key)" :maxlength="f.max"/>
    </label>
    <div v-if="modelValue.pais==='BR'" class="postal wide" aria-live="polite">
      <button class="erp-button erp-button--secondary" type="button" @click="lookup" :disabled="busy || !validCep">{{busy ? tr('Consultando CEP…') : tr('Conferir e completar pelo CEP')}}</button>
      <p v-if="message">{{tr(message)}}</p>
      <template v-if="conflicts.length">
        <p class="warning">{{ tr('O endereço informado difere da consulta. Seus dados foram mantidos:') }}</p>
        <ul><li v-for="c in conflicts" :key="c.field">{{tr(labels[c.field] || c.field)}}{{ tr(': informado “') }}{{c.provided}}{{ tr('”; ViaCEP: “') }}{{c.suggested}}”.</li></ul>
        <p>{{ tr('Confira o CEP com o cliente e corrija o campo correspondente antes de imprimir ou emitir a etiqueta.') }}</p>
      </template>
      <small>{{ tr('A consulta preenche campos vazios. Número, complemento e CPF permanecem como você informou.') }}</small>
    </div>
  </div>
</template>
<script setup lang="ts">
import {computed,ref,watch,nextTick} from 'vue'
import api from '@/services/api'
import { useAddressI18n } from './i18n'
import type {AddressData} from './types'
const {tr}=useAddressI18n()
const props=defineProps<{modelValue:AddressData;nameLabel?:string}>(),emit=defineEmits<{(e:'update:modelValue',v:AddressData):void}>()
const busy=ref(false),message=ref(''),conflicts=ref<{field:string;provided:string;suggested:string}[]>([])
const validCep=computed(()=>/^[0-9]{8}$/.test(props.modelValue.cep.replace(/[\s-]/g,'')))
const labels:Record<string,string>={endereco:'Rua',bairro:'Bairro',cidade:'Cidade',estado:'UF'}
let sequence=0
function update(key:string,value:string){emit('update:modelValue',{...props.modelValue,[key]:value})}
watch(()=>JSON.stringify(props.modelValue),()=>{sequence++;busy.value=false;message.value='';conflicts.value=[]})
function onBlur(key:string){if(key==='cep' && props.modelValue.pais==='BR' && validCep.value)lookup()}
async function lookup(){
  if(!validCep.value || props.modelValue.pais!=='BR')return
  const current=++sequence,original=JSON.stringify(props.modelValue)
  busy.value=true;message.value='';conflicts.value=[]
  try{
    const {data}=await api.post('/api/address-manager/postal-code',props.modelValue)
    // A slow response must not overwrite edits or a different recipient.
    if(current!==sequence || original!==JSON.stringify(props.modelValue))return
    if(data.status==='found'){
      if(data.filled.length || data.data.cep!==props.modelValue.cep){
        emit('update:modelValue',data.data)
        await nextTick()
        if(JSON.stringify(props.modelValue)!==JSON.stringify(data.data))return
      }
      conflicts.value=data.conflicts
      message.value=data.conflicts.length ? '' : data.filled.length ? 'Dados disponíveis preenchidos pelo ViaCEP. Confira o endereço.' : 'Conferência concluída. CEPs gerais podem não informar rua ou bairro.'
    }else message.value=({invalid:'Informe um CEP brasileiro com oito dígitos.',not_found:'CEP não encontrado. Confira os oito dígitos com o cliente.',skipped:'Consulta CEP não se aplica a este país.'} as Record<string,string>)[data.status] || 'Não foi possível consultar o CEP. Você pode preencher os dados e tentar novamente.'
  }catch{if(current===sequence)message.value='Não foi possível consultar o CEP. Você pode preencher os dados e tentar novamente.'}
  finally{if(current===sequence || !busy.value)busy.value=false}
}
const fields:{key:keyof AddressData;label:string;max:number}[]=[{key:'cep',label:'CEP (Brasil)',max:15},{key:'telefone',label:'Telefone',max:40},{key:'cpf',label:'CPF / documento (opcional na impressão)',max:20},{key:'endereco',label:'Rua / endereço (opcional para PY)',max:250},{key:'numero',label:'Número',max:10},{key:'bairro',label:'Bairro',max:60},{key:'complemento',label:'Complemento',max:60},{key:'cidade',label:'Cidade',max:100},{key:'estado',label:'UF / departamento',max:60},{key:'email',label:'E-mail',max:100}]
</script>
<style scoped>
.fields{display:grid;grid-template-columns:1fr 1fr;gap:0 15px}label{display:flex;flex-direction:column;gap:6px;font-size:12px;font-weight:600;color:#475569;margin:12px 0}.wide{grid-column:1/-1}input,select{border:1px solid #cbd5e1;border-radius:8px;padding:10px;background:white;color:#172033;min-width:0;font:inherit;font-weight:400}input:focus,select:focus{outline:2px solid #93c5fd}.postal{border:1px solid #dbeafe;background:#f8fafc;border-radius:8px;padding:12px;font-size:12px;color:#475569}.postal button{background:#eff6ff;border:1px solid #93c5fd;color:#1d4ed8;border-radius:6px;padding:8px 12px;cursor:pointer}.postal button:disabled{opacity:.5;cursor:default}.postal p{margin:9px 0}.postal small{display:block;margin-top:8px}.warning{color:#92400e}.postal ul{margin:8px 0;padding-left:18px}@media(max-width:420px){.fields{grid-template-columns:1fr}.wide{grid-column:auto}}
</style>
