import type { TemplateInput, TemplateQuery } from '../types/hengxin'
import { getService } from './hengxin/client'
export async function listTemplates(query: TemplateQuery) { return (await getService()).listTemplates(query) }
export async function getTemplate(id: string) { return (await getService()).getTemplate(id) }
export async function saveTemplate(input: TemplateInput) { return (await getService()).saveTemplate(input) }
export async function deleteTemplate(id: string) { return (await getService()).deleteTemplate(id) }
