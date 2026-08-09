import { Router } from 'express'
import { personaCatalog } from '../data/personas.js'

export const personaRouter = Router()

personaRouter.get('/', (_req, res) => {
  res.json(personaCatalog)
})
