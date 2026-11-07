import { Component, Input, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { TerritorialService, DepartamentoTerritorial, TerritorialResponse } from '../../service/territorial.service';
import { MapaColombiaComponent } from './mapa-colombia';

export const INDICADORES = [
  { id: 'n_contratos', label: 'Número de contratos' },
  { id: 'valor_total', label: 'Valor total contratado' },
  { id: 'poblacion_total', label: 'Población total' },
  { id: 'total_hombres', label: 'Total de hombres' },
  { id: 'total_mujeres', label: 'Total de mujeres' },
  { id: 'contratos_por_100k', label: 'Contratos por cada 100.000 habitantes' },
  { id: 'valor_por_habitante', label: 'Valor contratado por habitante' }
] as const;

type IndicadorId = typeof INDICADORES[number]['id'];

@Component({
  selector: 'app-mapa-territorial',
  standalone: true,
  imports: [CommonModule, MapaColombiaComponent],
  templateUrl: './mapa-territorial.html',
  styleUrl: './mapa-territorial.scss',
  host: { '[class.en-chat]': 'compacto' }
})
export class MapaTerritorialComponent implements OnInit {
  @Input() indicadorInicial: string | null = null;
  @Input() codigoDaneInicial: string | null = null;
  @Input() compacto = false;

  readonly indicadores = INDICADORES;
  indicador = signal<IndicadorId>('n_contratos');
  datos = signal<TerritorialResponse | null>(null);
  geojson = signal<any>(null);
  error = signal<string | null>(null);
  cargando = signal(true);
  seleccionado = signal<DepartamentoTerritorial | null>(null);
  tooltip = signal<{ depto: DepartamentoTerritorial; x: number; y: number } | null>(null);

  constructor(
    private territorial: TerritorialService,
    private http: HttpClient
  ) {}

  ngOnInit() {
    if (this.esIndicador(this.indicadorInicial)) {
      this.indicador.set(this.indicadorInicial);
    }
    this.territorial.getDepartamentos().subscribe({
      next: (res) => {
        this.datos.set(res);
        this.cargando.set(false);
        if (this.codigoDaneInicial) this.onSeleccionar(this.codigoDaneInicial);
      },
      error: () => {
        this.error.set('No fue posible cargar los indicadores territoriales.');
        this.cargando.set(false);
      }
    });
    this.http.get('/geo/colombia-departamentos.geojson').subscribe({
      next: (geo) => this.geojson.set(geo),
      error: () => this.error.set('No fue posible cargar el mapa de departamentos.')
    });
  }

  private esIndicador(valor: string | null): valor is IndicadorId {
    return Boolean(valor && INDICADORES.some((i) => i.id === valor));
  }

  valoresMapa(): Record<string, number | null> {
    const out: Record<string, number | null> = {};
    const clave = this.indicador();
    for (const d of this.datos()?.departamentos || []) {
      const v = d[clave];
      out[d.codigo_dane] = typeof v === 'number' && Number.isFinite(v) ? v : null;
    }
    return out;
  }

  onSeleccionar(codigo: string) {
    const d = this.datos()?.departamentos.find((x) => x.codigo_dane === codigo) || null;
    this.seleccionado.set(d);
  }

  onCursor(ev: { codigo: string; x: number; y: number } | null) {
    if (!ev) {
      this.tooltip.set(null);
      return;
    }
    const d = this.datos()?.departamentos.find((x) => x.codigo_dane === ev.codigo);
    this.tooltip.set(d ? { depto: d, x: ev.x, y: ev.y } : null);
  }

  etiquetaIndicador(): string {
    return INDICADORES.find((i) => i.id === this.indicador())?.label || '';
  }

  formato(valor: number | null, tipo: 'entero' | 'cop' | 'decimal' = 'entero'): string {
    if (valor == null || !Number.isFinite(valor)) return 'No disponible';
    if (tipo === 'cop') {
      return new Intl.NumberFormat('es-CO', {
        style: 'currency',
        currency: 'COP',
        maximumFractionDigits: 0
      }).format(valor);
    }
    if (tipo === 'decimal') {
      return new Intl.NumberFormat('es-CO', { maximumFractionDigits: 2 }).format(valor);
    }
    return new Intl.NumberFormat('es-CO', { maximumFractionDigits: 0 }).format(valor);
  }

  formatoValorTooltip(d: DepartamentoTerritorial): string {
    const clave = this.indicador();
    const v = d[clave];
    const n = typeof v === 'number' ? v : null;
    if (clave === 'valor_total' || clave === 'valor_por_habitante') return this.formato(n, 'cop');
    if (clave === 'contratos_por_100k') return this.formato(n, 'decimal');
    return this.formato(n);
  }

  tramosLeyenda(): { color: string; texto: string }[] {
    return [
      { color: '#fee5d9', texto: 'Menor' },
      { color: '#fcae91', texto: '' },
      { color: '#fb6a4a', texto: '' },
      { color: '#de2d26', texto: '' },
      { color: '#a50f15', texto: 'Mayor' }
    ];
  }
}
