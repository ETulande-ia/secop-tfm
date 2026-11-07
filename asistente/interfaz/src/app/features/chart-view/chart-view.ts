import { Component, Input, ElementRef, OnChanges } from '@angular/core';
import Chart from 'chart.js/auto';

const COP_KEYS = new Set(['valor', 'total_contratado', 'value']);

function esMoneda(spec: any): boolean {
  const y = String(spec?.y || '');
  const title = String(spec?.title || '');
  return COP_KEYS.has(y) || /COP|peso/i.test(title);
}

function formatoEje(valor: number, cop: boolean): string {
  const n = Number(valor);
  if (!Number.isFinite(n)) return '';
  const abs = Math.abs(n);
  if (cop || abs >= 10_000) {
    return new Intl.NumberFormat('es-CO', {
      notation: 'compact',
      compactDisplay: 'short',
      maximumFractionDigits: 1
    }).format(n);
  }
  return new Intl.NumberFormat('es-CO', { maximumFractionDigits: 2 }).format(n);
}

function etiquetaMultilinea(texto: string, max = 42): string | string[] {
  const s = String(texto ?? '').trim();
  if (s.length <= max) return s;
  const corte = s.lastIndexOf(' ', max);
  const a = s.slice(0, corte > 16 ? corte : max).trim();
  const b = s.slice(a.length).trim();
  return b.length ? [a, b.length > max ? `${b.slice(0, max - 1)}…` : b] : `${s.slice(0, max - 1)}…`;
}

@Component({
  selector: 'app-chart-view',
  standalone: true,
  template: `
    <div class="chart-frame" [style.height.px]="altura">
      <canvas></canvas>
    </div>
  `,
  styles: [`
    :host { display: block; width: 100%; }
    .chart-frame { position: relative; width: 100%; }
    canvas { display: block; }
  `]
})
export class ChartViewComponent implements OnChanges {

  @Input() data!: any[];
  @Input() spec!: any;

  altura = 320;
  private chart?: Chart;

  constructor(private el: ElementRef) {}

  ngOnChanges() {
    if (!this.data?.length || !this.spec) return;

    const horizontal = (this.spec.indexAxis || 'x') === 'y';
    this.altura = horizontal
      ? Math.max(360, this.data.length * 44 + 56)
      : 360;

    this.chart?.destroy();

    setTimeout(() => this.pintar(horizontal), 0);
  }

  private pintar(horizontal: boolean) {
    const canvas = this.el.nativeElement.querySelector('canvas');
    if (!canvas) return;

    const cop = esMoneda(this.spec);
    const xKey = this.spec.x;
    const yKey = this.spec.y;
    const etiquetas = this.data.map(d => {
      if (d.id_contrato && xKey === 'contrato') return String(d.id_contrato);
      return d[xKey];
    });

    this.chart?.destroy();
    this.chart = new Chart(canvas, {
      type: this.spec.type || 'bar',
      data: {
        labels: etiquetas,
        datasets: [{
          label: this.spec.title,
          data: this.data.map(d => d[yKey]),
          backgroundColor: '#c62828',
          borderRadius: 4,
          maxBarThickness: 28
        }]
      },
      options: {
        indexAxis: horizontal ? 'y' : 'x',
        responsive: true,
        maintainAspectRatio: false,
        layout: {
          padding: { top: 8, right: 16, bottom: 8, left: 4 }
        },
        plugins: {
          legend: { display: false },
          title: { display: false },
          tooltip: {
            callbacks: {
              title: (items: { dataIndex: number }[]) => {
                const i = items[0]?.dataIndex ?? 0;
                const row = this.data[i] || {};
                if (row.id_contrato) {
                  return `${row.id_contrato}${row.entidad ? ' — ' + row.entidad : ''}`;
                }
                return String(etiquetas[i] ?? '');
              },
              label: (item: { raw: unknown; dataIndex: number }) => {
                const n = Number(item.raw);
                const num = new Intl.NumberFormat('es-CO', {
                  maximumFractionDigits: cop ? 0 : 2
                }).format(n);
                const row = this.data[item.dataIndex] || {};
                if (cop) return ` ${num} COP`;
                if (yKey === 'score' || yKey === 'risk') return ` score_if ${num}`;
                return ` ${num}`;
              }
            }
          }
        },
        scales: {
          x: {
            beginAtZero: true,
            grid: { color: '#eef1f4' },
            ticks: {
              autoSkip: !horizontal,
              maxRotation: horizontal ? 0 : 40,
              font: { size: 11 },
              callback: (valor: string | number): string | string[] => {
                if (horizontal) return formatoEje(Number(valor), cop);
                const i = typeof valor === 'number' ? valor : Number(valor);
                return etiquetaMultilinea(String(etiquetas[i] ?? valor), 28);
              }
            }
          },
          y: {
            beginAtZero: !horizontal,
            afterFit: (ctx: { width: number }) => {
              if (horizontal) ctx.width = Math.max(ctx.width, 168);
            },
            grid: { color: horizontal ? '#eef1f4' : 'transparent' },
            ticks: {
              autoSkip: false,
              font: { size: 11 },
              callback: (valor: string | number): string | string[] => {
                if (!horizontal) return formatoEje(Number(valor), cop);
                const i = typeof valor === 'number' ? valor : Number(valor);
                return etiquetaMultilinea(String(etiquetas[i] ?? valor), 38);
              }
            }
          }
        }
      }
    });
  }
}
