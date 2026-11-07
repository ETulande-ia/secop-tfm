import { Component, ElementRef, signal, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ChatService, ChatSlots, ModoRag } from '../service/chat.service';
import { ChartViewComponent } from '../features/chart-view/chart-view';
import { MapaTerritorialComponent } from '../features/mapa-territorial/mapa-territorial';
import { MarkdownComponent } from 'ngx-markdown';

type Columna = { key: string; label: string; tipo: 'texto' | 'entero' | 'cop' | 'pct' | 'decimal' };

const ETIQUETAS: Record<string, string> = {
  modalidad: 'Modalidad',
  n: 'Contratos',
  pct: '%',
  entidad: 'Entidad',
  num_contratos: 'Contratos',
  total_contratado: 'Valor (COP)',
  rank: 'Puesto',
  id_contrato: 'Contrato',
  valor: 'Valor (COP)',
  score: 'score_if',
  city: 'Municipio',
  value: 'Valor (COP)',
  proveedor: 'Proveedor',
  entity: 'Entidad',
  days: 'Días',
  department: 'Departamento',
  risk: 'Score IF medio'
};

const COP = new Set(['valor', 'total_contratado', 'value']);
const ENTERO = new Set(['n', 'num_contratos', 'rank']);
const PCT = new Set(['pct']);
const DECIMAL = new Set(['score', 'risk', 'days']);
const ORDEN = [
  'rank', 'id_contrato', 'entidad', 'modalidad', 'proveedor', 'city', 'department',
  'n', 'pct', 'num_contratos', 'total_contratado', 'valor', 'value', 'score', 'risk', 'days'
];

@Component({
  selector: 'app-chat',
  standalone: true,
  imports: [CommonModule, ChartViewComponent, MapaTerritorialComponent, MarkdownComponent],
  templateUrl: './chat.html',
  styleUrls: ['./chat.scss'],
})
export class Chat {

  constructor(private chatService: ChatService) { }

  @ViewChild('messagesContainer') messagesContainer!: ElementRef;

  messages = signal<{ role: 'user' | 'assistant'; text: string }[]>([]);
  input = signal('');
  lastData = signal<any[] | null>(null);
  lastVisualization = signal<any | null>(null);
  lastSlots = signal<ChatSlots | null>(null);
  modoRag = signal<ModoRag>('auto');
  lastRuta = signal<string | null>(null);
  lastModoRag = signal<ModoRag | null>(null);

  readonly opcionesRag: { id: ModoRag; etiqueta: string; ayuda: string }[] = [
    { id: 'auto', etiqueta: 'Automático', ayuda: 'El asistente elige entre cifras SQL y manuales.' },
    { id: 'on', etiqueta: 'Con documentos', ayuda: 'Consulta los manuales en preguntas documentales. Las cifras siguen en SQL.' },
    { id: 'off', etiqueta: 'Sin documentos', ayuda: 'No consulta el corpus. No genera una respuesta legal sin evidencia.' }
  ];

  ayudaModo(): string {
    return this.opcionesRag.find(o => o.id === this.modoRag())?.ayuda || '';
  }

  send() {
    const value = this.input().trim();
    if (!value) return;

    this.lastVisualization.set(null);
    this.lastData.set(null);

    this.messages.update(m => [...m, { role: 'user', text: value }]);
    this.input.set('');

    this.chatService.sendMessage(value, this.lastSlots(), this.modoRag()).subscribe({
      next: (response) => {
        this.messages.update(m => [
          ...m,
          { role: 'assistant', text: this.textoLegible(response.text || '') }
        ]);

        const filas = Array.isArray(response.data) ? response.data : null;
        this.lastData.set(filas);
        this.lastVisualization.set(response.visualization || null);
        if (response.slots) this.lastSlots.set(response.slots);
        this.lastModoRag.set(response.modoRag || this.modoRag());
        this.lastRuta.set(response.ruta || null);
      },
      error: () => {
        this.messages.update(m => [
          ...m,
          { role: 'assistant', text: 'Error al obtener respuesta del servidor.' }
        ]);
      }
    });

    setTimeout(() => {
      this.messagesContainer.nativeElement.scrollTop =
        this.messagesContainer.nativeElement.scrollHeight;
    }, 0);
  }

  columnas(): Columna[] {
    const rows = this.lastData();
    if (!rows?.length) return [];
    const keys = Object.keys(rows[0])
      .filter(k => k !== 'contrato')
      .sort((a, b) => {
        const ia = ORDEN.indexOf(a);
        const ib = ORDEN.indexOf(b);
        return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib);
      });
    return keys
      .filter(k => ETIQUETAS[k] || typeof rows[0][k] !== 'object')
      .map(key => ({
        key,
        label: ETIQUETAS[key] || key,
        tipo: COP.has(key) ? 'cop'
          : PCT.has(key) ? 'pct'
          : ENTERO.has(key) ? 'entero'
          : DECIMAL.has(key) ? 'decimal'
          : 'texto'
      }));
  }

  esMapa(): boolean {
    return this.lastVisualization()?.type === 'mapa_territorial';
  }

  esGrafico(): boolean {
    const spec = this.lastVisualization();
    return Boolean(spec && spec.type !== 'mapa_territorial');
  }

  indicadorMapa(): string | null {
    return this.lastVisualization()?.indicador || null;
  }

  codigoMapa(): string | null {
    return this.lastVisualization()?.codigo_dane || null;
  }

  tituloGrafico(): string {
    return this.lastVisualization()?.titulo || this.lastVisualization()?.title || 'Visualización asociada';
  }

  notaGrafico(): string | null {
    const spec = this.lastVisualization();
    const rows = this.lastData();
    if (!spec || !rows?.length) return null;
    const y = spec.y;
    if (y === 'total_contratado' || y === 'value' || y === 'valor') {
      return 'El largo de las barras corresponde al valor contratado, en pesos colombianos (COP).';
    }
    if (y === 'n' || y === 'num_contratos') {
      return 'El largo de las barras corresponde al número de contratos.';
    }
    if (y === 'score' || y === 'risk') {
      return 'El largo de las barras corresponde al score Isolation Forest (mayor = más atípico estadísticamente).';
    }
    if (y === 'days') {
      return 'El largo de las barras corresponde a la duración media, en días.';
    }
    return null;
  }

  formatear(valor: unknown, tipo: Columna['tipo']): string {
    if (valor == null || valor === '') return '—';
    const n = Number(valor);
    if (tipo === 'texto' || !Number.isFinite(n)) return String(valor);
    if (tipo === 'cop') {
      return `${new Intl.NumberFormat('es-CO', { maximumFractionDigits: 0 }).format(n)} COP`;
    }
    if (tipo === 'pct') {
      return `${new Intl.NumberFormat('es-CO', { maximumFractionDigits: 2 }).format(n)} %`;
    }
    if (tipo === 'entero') {
      return new Intl.NumberFormat('es-CO', { maximumFractionDigits: 0 }).format(n);
    }
    return new Intl.NumberFormat('es-CO', { maximumFractionDigits: 4 }).format(n);
  }

  private textoLegible(text: string): string {
    if (!text) return '';
    if (!text.includes('\n') && text.length > 280) {
      return text.replace(/\. (?=[A-ZÁÉÍÓÚÜÑ])/g, '.\n\n');
    }
    const lines = text.split('\n').map(l => l.trim()).filter(l => l.length);
    if (lines.length < 3) return text;
    const resto = lines.slice(1);
    const yaLista = resto.every(l => /^(\d+\.\s|[-*]\s)/.test(l));
    if (yaLista) {
      return `${lines[0]}\n\n${resto.join('\n\n')}`;
    }
    return `${lines[0]}\n\n${resto.map(l => `- ${l}`).join('\n')}`;
  }
}
