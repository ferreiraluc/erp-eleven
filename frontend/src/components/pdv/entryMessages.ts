import { useI18n } from 'vue-i18n'

const messages: Record<string, [string, string, string]> = {
  customer: ['Cliente (opcional)', 'Cliente (opcional)', 'Customer (optional)'],
  search: ['Nome, telefone, documento ou CEP', 'Nombre, teléfono, documento o código postal', 'Name, phone, document or postal code'],
  hint: ['Digite ao menos 2 caracteres e selecione o cliente.', 'Escriba al menos 2 caracteres y seleccione el cliente.', 'Type at least 2 characters and select the customer.'],
  loading: ['Buscando clientes…', 'Buscando clientes…', 'Searching customers…'],
  linking: ['Associando cliente…', 'Asociando cliente…', 'Linking customer…'],
  empty: ['Nenhum cliente encontrado. Confira os dados ou tente outro contato.', 'No se encontraron clientes. Revise los datos o pruebe otro contacto.', 'No customers found. Check the details or try another contact.'],
  more: ['Há mais resultados. Refine a busca com mais dados.', 'Hay más resultados. Refine la búsqueda con más datos.', 'More results are available. Narrow your search with more details.'],
  failed: ['Não foi possível buscar clientes. Tente novamente.', 'No se pudo buscar clientes. Inténtelo de nuevo.', 'Could not search customers. Try again.'],
  selectFailed: ['Não foi possível associar o cliente. Atualize a busca e confira o cadastro.', 'No se pudo asociar el cliente. Actualice la búsqueda y revise el registro.', 'Could not link the customer. Refresh the search and check their record.'],
  remove: ['Remover cliente', 'Quitar cliente', 'Remove customer'],
  nameOnly: ['Usar somente o nome, sem cadastro', 'Usar solo el nombre, sin registro', 'Use name only, without linking a record'],
  unlinked: ['Nome sem cadastro', 'Nombre sin registro', 'Name only'],
  directory: ['Cadastro de clientes', 'Registro de clientes', 'Customer directory'],
  currency: ['Moeda do item', 'Moneda del artículo', 'Item currency'],
  price: ['Preço unitário', 'Precio unitario', 'Unit price'],
  conversion: ['Equivalente por unidade', 'Equivalente por unidad', 'Equivalent per unit'],
  rate: ['Câmbio aplicado', 'Cambio aplicado', 'Applied exchange rate'],
  invalidRate: ['Câmbio indisponível. Confira as taxas do PDV.', 'Cambio no disponible. Revise las tasas del PDV.', 'Exchange rate unavailable. Check the POS rates.'],
}

export function usePdvEntryText() {
  const { locale } = useI18n({ useScope: 'global' })
  return (key: string) => messages[key]?.[locale.value === 'es' ? 1 : locale.value === 'en' ? 2 : 0] || key
}
