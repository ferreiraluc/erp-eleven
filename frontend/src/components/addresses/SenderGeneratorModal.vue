<template>
  <div class="generator-overlay" @click.self="close">
    <section ref="dialog" class="generator-dialog" role="dialog" aria-modal="true" :aria-label="t('title')" tabindex="-1" @keydown.esc.prevent="close" @keydown.tab="trapFocus">
      <header><div><span class="eyebrow">4DEVS · {{ t('synthetic') }}</span><h2>{{ t('title') }}</h2></div><button class="erp-button erp-button--secondary erp-button--icon" type="button" :disabled="busy || saving" :aria-label="t('close')" @click="close"><X :size="20"/></button></header>
      <p class="intro">{{ t('intro') }}</p>
      <div class="origin-note"><Sparkles :size="17"/><p>{{ t('origin') }}</p></div>
      <p v-if="error" class="error" role="alert">{{ t('errors.' + error) }}</p>
      <div class="generate-controls">
        <label>{{ t('sex') }}<select v-model="options.sexo" :disabled="busy || saving"><option value="I">{{ t('random') }}</option><option value="M">{{ t('male') }}</option><option value="F">{{ t('female') }}</option></select></label>
        <label>{{ t('age') }}<input v-model.number="age" type="number" min="18" max="90" :placeholder="t('optional')" :disabled="busy || saving"/></label>
        <label>{{ t('state') }}<select v-model="options.estado" :disabled="busy || saving"><option value="">{{ t('random') }}</option><option v-for="state in BRAZIL_STATES" :key="state">{{ state }}</option></select></label>
        <button type="button" class="primary erp-button erp-button--primary" :disabled="busy || saving" @click="generate"><RefreshCw v-if="busy" :size="16" class="spin"/><Sparkles v-else :size="16"/>{{ busy ? t('generating') : t('generate') }}</button>
      </div>
      <details class="manual" :open="manualOpen">
        <summary @click.prevent="manualOpen = !manualOpen">{{ t('manualTitle') }}</summary>
        <p>{{ t('manualHelp') }}</p>
        <a :href="FOURDEVS_PAGE" target="_blank" rel="noopener noreferrer">{{ t('openProvider') }} <ExternalLink :size="14"/></a>
        <label>{{ t('pasteJson') }}<textarea v-model="jsonInput" maxlength="30000" rows="5" placeholder='[{"nome":"...","cpf":"...","endereco":"..."}]' spellcheck="false" :disabled="busy || saving"/></label>
        <button class="erp-button erp-button--secondary" type="button" :disabled="busy || saving || !jsonInput.trim()" @click="importJson">{{ t('importJson') }}</button>
      </details>
      <form v-if="preview" class="review" @submit.prevent="save">
        <div class="review-heading"><div><h3>{{ t('reviewTitle') }}</h3><p>{{ t('reviewHelp') }}</p></div><span class="badge">{{ t('notSaved') }}</span></div>
        <label>{{ t('label') }}<input v-model="name" required maxlength="100" :disabled="saving"/></label>
        <div class="person-grid">
          <label v-for="field in senderFields" :key="field.key" :class="{wide:field.key==='endereco'}">{{ t('fields.' + field.key) }}
            <select v-if="field.key==='estado'" v-model="person[field.key]" :disabled="saving"><option value="">{{ t('optional') }}</option><option v-for="state in BRAZIL_STATES" :key="state">{{ state }}</option></select>
            <input v-else v-model="person[field.key]" :maxlength="field.max" :required="field.key==='nome'" :disabled="saving"/>
          </label>
          <label>{{ t('complement') }}<input v-model="complement" maxlength="60" :disabled="saving"/></label>
        </div>
        <details class="full-person"><summary>{{ t('fullPerson') }}</summary><p>{{ t('extraInfo') }}</p><div class="person-grid"><label v-for="key in extraFields" :key="key">{{ t('fields.' + key) }}<input v-model="person[key]" maxlength="250" :disabled="saving"/></label></div></details>
        <div class="print-preview"><span>{{ t('senderPreview') }}</span><p>{{ printedLines.join('\n') }}</p></div>
        <label class="check"><input v-model="active" type="checkbox" :disabled="saving"/>{{ t('active') }}</label>
        <label class="check approval"><input v-model="approved" type="checkbox" required :disabled="saving"/>{{ t('approval') }}</label>
        <footer><button class="erp-button erp-button--secondary" type="button" :disabled="saving" @click="close">{{ t('discard') }}</button><button class="primary erp-button erp-button--primary" :disabled="!approved || saving || busy"><CheckCircle2 :size="17"/>{{ saving ? t('saving') : t('save') }}</button></footer>
      </form>
      <div v-else class="empty"><UserRound :size="35"/><h3>{{ t('emptyTitle') }}</h3><p>{{ t('emptyHelp') }}</p></div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { CheckCircle2, ExternalLink, RefreshCw, Sparkles, UserRound, X } from 'lucide-vue-next'
import { blankAddress } from './types'
import { BRAZIL_STATES, FOURDEVS_PAGE, generatePerson, generationError, importPerson, saveGeneratedSender } from '@/services/senderGenerator'
import type { GenerationOptions, PersonPreview } from '@/services/senderGenerator'

const emit = defineEmits<{ close: []; saved: [id: string] }>()
const messages = {
  pt: {
    title:'Gerar pessoa e revisar remetente',synthetic:'DADOS SINTÉTICOS',close:'Fechar',intro:'Gere uma pessoa completa no 4Devs ou importe o JSON. Revise e edite os dados antes de aprovar o cadastro.',
    origin:'Origem sintética: os dados gerados não comprovam identidade. O cadastro conserva esse aviso; nenhum envio, etiqueta ou impressão será realizado aqui.',sex:'Sexo',random:'Aleatório',male:'Masculino',female:'Feminino',age:'Idade',state:'Estado',optional:'Opcional',generate:'Gerar pessoa',generating:'Gerando…',
    manualTitle:'Abrir o 4Devs e importar JSON',manualHelp:'A geração usa o formulário público do 4Devs; a API oficial ainda não foi lançada. Se houver limite ou verificação no site, gere uma pessoa lá, selecione JSON e copie a resposta para este campo.',openProvider:'Abrir gerador do 4Devs',pasteJson:'JSON de uma pessoa',importJson:'Importar para revisão',
    reviewTitle:'Conferir dados',reviewHelp:'Somente os campos úteis ao remetente serão salvos.',notSaved:'Ainda não salvo',label:'Identificação no gestor',complement:'Complemento',fullPerson:'Ver e editar a pessoa completa',extraInfo:'RG, nascimento, filiação, senha e características ficam apenas nesta prévia. Não são salvos no ERP.',senderPreview:'Prévia do bloco de remetente',active:'Deixar remetente ativo',approval:'Revisei os dados e aprovo salvar este remetente, identificado como origem sintética.',discard:'Descartar',saving:'Salvando…',save:'Aprovar e salvar remetente',emptyTitle:'A pessoa aparecerá aqui',emptyHelp:'Gerar ou importar prepara uma prévia. O cadastro só acontece após sua aprovação.',
    fields:{nome:'Nome',cpf:'CPF',cep:'CEP',endereco:'Rua / endereço',numero:'Número',bairro:'Bairro',cidade:'Cidade',estado:'UF',celular:'Celular',telefone_fixo:'Telefone fixo',email:'E-mail',idade:'Idade',rg:'RG',data_nasc:'Nascimento',sexo:'Sexo',signo:'Signo',mae:'Mãe',pai:'Pai',senha:'Senha gerada',altura:'Altura',peso:'Peso',tipo_sanguineo:'Tipo sanguíneo',cor:'Cor favorita'},
    errors:{rate_limited:'Aguarde alguns segundos antes de gerar outra pessoa.',provider_blocked:'O 4Devs limitou o acesso ou pediu verificação. Abra o site e importe o JSON; não tentamos contornar o bloqueio.',provider_unavailable:'O formulário do 4Devs está indisponível. Tente mais tarde ou importe o JSON do site.',one_person:'Importe exatamente uma pessoa por vez.',invalid_json:'JSON inválido ou campos incompatíveis. Copie o JSON de uma pessoa e confira os dados.',request_conflict:'Esta confirmação já salvou outros dados. Confira a lista antes de tentar novamente.',sender_bounds:'Cada linha do remetente pode ter até 150 caracteres. Encurte o endereço e confira a prévia.',review_required:'Revise o nome e os dados brasileiros antes de salvar.',request_failed:'Não foi possível concluir. Confira os campos e tente novamente.',invalid_age:'Informe uma idade entre 18 e 90 anos, ou deixe em branco.'},
  },
  es: {
    title:'Generar persona y revisar remitente',synthetic:'DATOS SINTÉTICOS',close:'Cerrar',intro:'Genere una persona completa en 4Devs o importe el JSON. Revise y edite los datos antes de aprobar el registro.',
    origin:'Origen sintético: los datos generados no acreditan identidad. El registro conserva esta indicación; aquí no se envía, emite ni imprime nada.',sex:'Sexo',random:'Aleatorio',male:'Masculino',female:'Femenino',age:'Edad',state:'Estado',optional:'Opcional',generate:'Generar persona',generating:'Generando…',
    manualTitle:'Abrir 4Devs e importar JSON',manualHelp:'La generación usa el formulario público de 4Devs; la API oficial aún no está disponible. Si el sitio exige verificación o limita el acceso, genere allí una persona, seleccione JSON y copie la respuesta aquí.',openProvider:'Abrir generador de 4Devs',pasteJson:'JSON de una persona',importJson:'Importar para revisar',
    reviewTitle:'Revisar datos',reviewHelp:'Solo se guardarán los campos útiles para el remitente.',notSaved:'Sin guardar',label:'Nombre en el gestor',complement:'Complemento',fullPerson:'Ver y editar la persona completa',extraInfo:'RG, nacimiento, filiación, contraseña y características permanecen solo en esta vista previa. No se guardan en el ERP.',senderPreview:'Vista previa del remitente',active:'Dejar remitente activo',approval:'Revisé los datos y apruebo guardar este remitente, identificado como de origen sintético.',discard:'Descartar',saving:'Guardando…',save:'Aprobar y guardar remitente',emptyTitle:'La persona aparecerá aquí',emptyHelp:'Generar o importar prepara una vista previa. Solo se guarda después de su aprobación.',
    fields:{nome:'Nombre',cpf:'CPF',cep:'Código postal',endereco:'Calle / dirección',numero:'Número',bairro:'Barrio',cidade:'Ciudad',estado:'UF',celular:'Celular',telefone_fixo:'Teléfono fijo',email:'Correo electrónico',idade:'Edad',rg:'RG',data_nasc:'Nacimiento',sexo:'Sexo',signo:'Signo',mae:'Madre',pai:'Padre',senha:'Contraseña generada',altura:'Altura',peso:'Peso',tipo_sanguineo:'Grupo sanguíneo',cor:'Color favorito'},
    errors:{rate_limited:'Espere unos segundos antes de generar otra persona.',provider_blocked:'4Devs limitó el acceso o solicitó verificación. Abra el sitio e importe el JSON; no eludimos el bloqueo.',provider_unavailable:'El formulario de 4Devs no está disponible. Intente más tarde o importe el JSON del sitio.',one_person:'Importe exactamente una persona por vez.',invalid_json:'JSON inválido o campos incompatibles. Copie el JSON de una persona y revise los datos.',request_conflict:'Esta confirmación ya guardó otros datos. Revise la lista antes de intentar de nuevo.',sender_bounds:'Cada línea del remitente admite hasta 150 caracteres. Acorte la dirección y revise la vista previa.',review_required:'Revise el nombre y los datos brasileños antes de guardar.',request_failed:'No se pudo completar. Revise los campos e intente de nuevo.',invalid_age:'Ingrese una edad entre 18 y 90 años o deje el campo vacío.'},
  },
  en: {
    title:'Generate person and review sender',synthetic:'SYNTHETIC DATA',close:'Close',intro:'Generate a complete person with 4Devs or import its JSON. Review and edit the data before approving the record.',
    origin:'Synthetic source: generated data does not establish identity. The record retains this label; nothing is shipped, purchased or printed here.',sex:'Sex',random:'Random',male:'Male',female:'Female',age:'Age',state:'State',optional:'Optional',generate:'Generate person',generating:'Generating…',
    manualTitle:'Open 4Devs and import JSON',manualHelp:'Generation uses the public 4Devs form; its official API is not available yet. If the site requires verification or limits access, generate a person there, choose JSON and paste the response here.',openProvider:'Open 4Devs generator',pasteJson:'One person’s JSON',importJson:'Import for review',
    reviewTitle:'Review data',reviewHelp:'Only fields needed for the sender will be saved.',notSaved:'Not saved yet',label:'Name in the manager',complement:'Address complement',fullPerson:'View and edit the complete person',extraInfo:'ID, birth date, parents, password and characteristics remain in this preview only. They are not saved in the ERP.',senderPreview:'Sender block preview',active:'Keep sender active',approval:'I reviewed the data and approve saving this sender, labeled as a synthetic source.',discard:'Discard',saving:'Saving…',save:'Approve and save sender',emptyTitle:'The person will appear here',emptyHelp:'Generating or importing prepares a preview. Saving requires your approval.',
    fields:{nome:'Name',cpf:'CPF',cep:'Postal code',endereco:'Street / address',numero:'Number',bairro:'District',cidade:'City',estado:'State',celular:'Mobile',telefone_fixo:'Landline',email:'Email',idade:'Age',rg:'ID',data_nasc:'Birth date',sexo:'Sex',signo:'Zodiac sign',mae:'Mother',pai:'Father',senha:'Generated password',altura:'Height',peso:'Weight',tipo_sanguineo:'Blood type',cor:'Favorite color'},
    errors:{rate_limited:'Wait a few seconds before generating another person.',provider_blocked:'4Devs limited access or requested verification. Open the site and import JSON; we do not bypass the block.',provider_unavailable:'The 4Devs form is unavailable. Try later or import JSON from the site.',one_person:'Import exactly one person at a time.',invalid_json:'Invalid JSON or incompatible fields. Copy one person’s JSON and check the data.',request_conflict:'This confirmation already saved different data. Check the list before trying again.',sender_bounds:'Each sender line can contain up to 150 characters. Shorten the address and review the preview.',review_required:'Review the name and Brazilian address before saving.',request_failed:'Could not complete the request. Check the fields and try again.',invalid_age:'Enter an age between 18 and 90, or leave it blank.'},
  },
}
const { t } = useI18n({ useScope: 'local', messages, inheritLocale: true, fallbackLocale: 'pt' })
const dialog = ref<HTMLElement | null>(null), preview = ref<PersonPreview | null>(null), person = ref<Record<string, string>>({})
const options = ref<GenerationOptions>({ sexo: 'I', idade: null, estado: 'PR' }), age = ref<number | ''>('')
const busy = ref(false), saving = ref(false), error = ref(''), approved = ref(false), active = ref(true), name = ref(''), complement = ref('')
const jsonInput = ref(''), manualOpen = ref(false), requestKey = ref(crypto.randomUUID())
const senderFields = [{key:'nome',max:120},{key:'cpf',max:20},{key:'cep',max:15},{key:'endereco',max:250},{key:'numero',max:10},{key:'bairro',max:60},{key:'cidade',max:100},{key:'estado',max:2},{key:'celular',max:40},{key:'telefone_fixo',max:40},{key:'email',max:100}]
const extraFields = ['idade','rg','data_nasc','sexo','signo','mae','pai','senha','altura','peso','tipo_sanguineo','cor']
const senderData = computed(() => ({ ...blankAddress('BR'), nome:person.value.nome || '',cpf:person.value.cpf || '',cep:person.value.cep || '',endereco:person.value.endereco || '',numero:person.value.numero || '',bairro:person.value.bairro || '',cidade:person.value.cidade || '',estado:person.value.estado || '',email:person.value.email || '',telefone:person.value.celular || person.value.telefone_fixo || '',complemento:complement.value }))
const printedLines = computed(() => { const d=senderData.value;return[d.nome,[d.endereco,d.numero].filter(Boolean).join(', '),d.bairro,d.complemento,[d.cidade,d.estado].filter(Boolean).join(' - '),d.cep?'CEP '+d.cep:'',d.cpf?'CPF: '+d.cpf:''].filter(Boolean) })
watch([person,name,complement,active], () => { approved.value=false }, { deep:true })
function accept(result:PersonPreview) { preview.value=result;person.value={...result.person};name.value=(result.person.nome || '').slice(0,100);complement.value='';approved.value=false;requestKey.value=crypto.randomUUID();jsonInput.value='' }
function showError(cause:unknown) { const code=generationError(cause);error.value=Object.hasOwn(messages.pt.errors,code)?code:'request_failed';if(code==='provider_blocked'||code==='provider_unavailable')manualOpen.value=true }
async function generate() {
  if(age.value!=='' && (!Number.isInteger(age.value)||age.value<18||age.value>90)){error.value='invalid_age';return}
  busy.value=true;approved.value=false;error.value=''
  try { accept(await generatePerson({...options.value,idade:age.value===''?null:age.value})) } catch(cause) {showError(cause)} finally {busy.value=false}
}
async function importJson() { busy.value=true;approved.value=false;error.value='';try {accept(await importPerson(jsonInput.value))}catch(cause){showError(cause)}finally{busy.value=false} }
async function save() { if(!preview.value||!approved.value||saving.value)return;saving.value=true;error.value='';try {const result=await saveGeneratedSender({request_key:requestKey.value,approved:true,source:preview.value.source,name:name.value,data:senderData.value,active:active.value});emit('saved',result.id)}catch(cause){showError(cause)}finally{saving.value=false} }
function close() { if(!busy.value&&!saving.value)emit('close') }
function trapFocus(event:KeyboardEvent) {
  const controls=Array.from(dialog.value?.querySelectorAll<HTMLElement>('button:not(:disabled),input:not(:disabled),select:not(:disabled),textarea:not(:disabled),a[href],summary') || []).filter(element=>element.getClientRects().length>0)
  const first=controls[0],last=controls[controls.length-1]
  if(!first||!last)return
  if(event.shiftKey&&(document.activeElement===first||document.activeElement===dialog.value)){event.preventDefault();last.focus()}
  else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus()}
}
const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null
onMounted(() => dialog.value?.focus())
onUnmounted(() => { person.value={};jsonInput.value='';previousFocus?.focus() })
</script>

<style scoped>
.generator-overlay{position:fixed;inset:0;z-index:1100;display:flex;align-items:center;justify-content:center;padding:22px;background:#0f172a88;backdrop-filter:blur(3px)}.generator-dialog{width:820px;max-width:100%;max-height:92vh;overflow-y:auto;padding:26px;background:#fff;color:#172033;border-radius:16px;box-shadow:0 20px 70px #0003;outline:none}.generator-dialog header,.review-heading,footer{display:flex;align-items:center;justify-content:space-between;gap:16px}.generator-dialog header{border-bottom:1px solid #e2e8f0;padding-bottom:18px}.eyebrow{font-size:10px;font-weight:750;letter-spacing:.12em;color:#64748b}h2{margin:6px 0 0;font-size:22px;letter-spacing:-.5px}h3{margin:0 0 7px;font-size:17px}p{font-size:13px;line-height:1.6;color:#64748b}.intro{margin:18px 0}.origin-note{display:flex;gap:10px;align-items:start;background:#eff6ff;border:1px solid #bfdbfe;padding:12px 14px;border-radius:10px}.origin-note svg{color:#2563eb;flex-shrink:0;margin-top:3px}.origin-note p{margin:0;color:#1e40af;font-size:12px}.generate-controls{display:grid;grid-template-columns:1fr .8fr 1fr auto;gap:12px;align-items:end;margin:18px 0}.generate-controls label{margin:0}label{display:flex;flex-direction:column;gap:6px;margin:12px 0;font-size:12px;font-weight:600;color:#475569}input,select,textarea{font:inherit;font-size:13px;font-weight:400;padding:10px;border:1px solid #cbd5e1;border-radius:8px;color:#172033;background:#fff;min-width:0;width:100%;box-sizing:border-box}input:focus,select:focus,textarea:focus{outline:2px solid #93c5fd;outline-offset:1px}button,a{display:inline-flex;align-items:center;justify-content:center;gap:7px;padding:10px 12px;border:1px solid #dce3ed;border-radius:8px;background:#fff;color:#334155;font:inherit;font-size:12px;font-weight:600;text-decoration:none;cursor:pointer}button:hover,a:hover{background:#f1f5f9}button:disabled{opacity:.5;cursor:not-allowed}button.primary{background:#2563eb;border-color:#2563eb;color:#fff}.manual{border:1px solid #e2e8f0;border-radius:10px;padding:13px 15px;background:#f8fafc}.manual summary,.full-person summary{cursor:pointer;font-size:13px;font-weight:650;color:#2563eb}.manual textarea{font-family:monospace;font-size:12px}.review{margin-top:28px}.badge{white-space:nowrap;background:#fef3c7;color:#92400e;font-size:10px;font-weight:700;padding:6px 9px;border-radius:6px}.review-heading p{margin:0 0 8px}.person-grid{display:grid;grid-template-columns:1fr 1fr;gap:0 16px}.wide{grid-column:1/-1}.full-person{border-block:1px solid #e2e8f0;margin:20px 0;padding:15px 0}.print-preview{padding:16px;background:#f8fafc;border:1px dashed #cbd5e1;border-radius:10px}.print-preview span{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:#64748b}.print-preview p{white-space:pre-line;color:#172033;margin-bottom:0;overflow-wrap:anywhere}.check{flex-direction:row;align-items:start;gap:9px;line-height:1.5}.check input{width:16px;height:16px;flex-shrink:0;margin:0}.approval{background:#eff6ff;padding:13px;border-radius:8px;color:#1e40af}footer{justify-content:flex-end;border-top:1px solid #e2e8f0;padding-top:18px;margin-top:20px}.empty{text-align:center;padding:36px 15px;color:#94a3b8}.empty svg{margin:0 auto 12px}.empty p{margin-bottom:0}.error{padding:12px 14px;background:#fff1f2;color:#9f1239;border-radius:8px}.spin{animation:spin 1s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}@media(max-width:620px){.generator-overlay{padding:8px}.generator-dialog{padding:18px}.generate-controls{grid-template-columns:1fr 1fr}.generate-controls .primary{min-height:38px}.person-grid{gap:0 10px}h2{font-size:18px}.review-heading{align-items:start}.badge{white-space:normal;text-align:center}footer{flex-wrap:wrap}}@media(max-width:400px){.person-grid{grid-template-columns:1fr}.wide{grid-column:auto}}
</style>
