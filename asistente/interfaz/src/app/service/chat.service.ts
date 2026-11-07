import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface ChatSlots {
  operacion?: string | null;
  metrica?: string | null;
  territorio?: string | null;
  entidad?: string | null;
  modalidad?: string | null;
  periodo?: string | null;
  idContrato?: string | null;
}

export type ModoRag = 'auto' | 'on' | 'off';

export interface ChatResponse {
  text: string;
  data?: any;
  visualization?: any;
  slots?: ChatSlots | null;
  intent?: string | null;
  modoRag?: ModoRag;
  ruta?: string | null;
  referencias?: unknown[] | null;
}

@Injectable({ providedIn: 'root' })
export class ChatService {

  // Relativa: nginx (o el proxy de ng serve) reenvía /api al orquestador.
  private apiUrl = '/api/chat';

  constructor(private http: HttpClient) {}

  sendMessage(
    query: string,
    contexto?: ChatSlots | null,
    modoRag: ModoRag = 'auto'
  ): Observable<ChatResponse> {
    return this.http.post<ChatResponse>(this.apiUrl, {
      query,
      contexto: contexto || undefined,
      modoRag
    });
  }
}
