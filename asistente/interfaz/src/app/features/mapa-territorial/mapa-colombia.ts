import {
  Component,
  ElementRef,
  EventEmitter,
  Input,
  OnChanges,
  OnDestroy,
  Output
} from '@angular/core';
import { geoMercator, geoPath } from 'd3';
import { scaleQuantile } from 'd3';
import { select } from 'd3';

@Component({
  selector: 'app-mapa-colombia',
  standalone: true,
  template: `<div class="mapa-host" #host></div>`,
  styles: [`
    :host { display: block; width: 100%; height: 560px; }
    .mapa-host { width: 100%; height: 560px; }
    :host ::ng-deep path.depto { stroke: #fff; stroke-width: 0.8; cursor: pointer; }
    :host ::ng-deep path.depto.sel { stroke: #1f2937; stroke-width: 2; }
  `]
})
export class MapaColombiaComponent implements OnChanges, OnDestroy {
  @Input() geojson: any;
  @Input() valores: Record<string, number | null> = {};
  @Input() seleccionado: string | null = null;
  @Output() seleccionar = new EventEmitter<string>();
  @Output() cursor = new EventEmitter<{ codigo: string; x: number; y: number } | null>();

  private svg?: ReturnType<typeof select<SVGSVGElement, unknown>>;
  private ro?: ResizeObserver;
  private lastSize = '';

  constructor(private el: ElementRef<HTMLElement>) {}

  ngOnChanges() {
    this.dibujar();
  }

  ngOnDestroy() {
    this.ro?.disconnect();
  }

  private dibujar() {
    const host = this.el.nativeElement.querySelector('.mapa-host') as HTMLElement | null;
    if (!host || !this.geojson?.features) return;

    if (!this.ro) {
      this.ro = new ResizeObserver(() => {
        const next = `${Math.max(Math.floor(host.clientWidth), 320)}x560`;
        if (!host.clientWidth || next === this.lastSize) return;
        this.dibujar();
      });
      this.ro.observe(host);
    }
    if (!host.clientWidth) return;

    const w = Math.max(Math.floor(host.clientWidth), 320);
    const h = 560;
    const sizeKey = `${w}x${h}`;
    select(host).selectAll('svg').remove();

    this.svg = select(host)
      .append('svg')
      .attr('viewBox', `0 0 ${w} ${h}`)
      .attr('preserveAspectRatio', 'xMidYMid meet')
      .attr('width', '100%')
      .attr('height', '100%');

    const continente = {
      type: 'FeatureCollection',
      features: this.geojson.features.filter((f: any) => this.codigo(f) !== '88')
    };
    const islas = {
      type: 'FeatureCollection',
      features: this.geojson.features.filter((f: any) => this.codigo(f) === '88')
    };
    const projection = geoMercator().fitExtent([[12, 12], [w - 12, h - 12]], continente as any);
    const path = geoPath(projection);
    const nums = Object.values(this.valores).filter((v): v is number => v != null && Number.isFinite(v));
    const colores = ['#fee5d9', '#fcae91', '#fb6a4a', '#de2d26', '#a50f15'];
    const escala = nums.length ? scaleQuantile<string>().domain(nums).range(colores) : null;

    const pintar = (
      feats: any[],
      generador: any
    ) => {
      this.svg!.append('g')
        .selectAll('path')
        .data(feats)
        .join('path')
        .attr('class', (d: any) => `depto${this.codigo(d) === this.seleccionado ? ' sel' : ''}`)
        .attr('data-dane', (d: any) => this.codigo(d))
        .attr('d', generador as any)
        .attr('fill', (d: any) => {
          const v = this.valores[this.codigo(d)];
          if (v == null || !escala) return '#e5e7eb';
          return escala(v);
        })
        .on('mousemove', (event: MouseEvent, d: any) => {
          this.cursor.emit({ codigo: this.codigo(d), x: event.clientX, y: event.clientY });
        })
        .on('mouseleave', () => this.cursor.emit(null))
        .on('click', (_event: MouseEvent, d: any) => this.seleccionar.emit(this.codigo(d)));
    };

    pintar(continente.features, path);

    if (islas.features.length) {
      const caja = { x: 16, y: 16, w: 150, h: 120 };
      this.svg.append('rect')
        .attr('x', caja.x)
        .attr('y', caja.y)
        .attr('width', caja.w)
        .attr('height', caja.h)
        .attr('rx', 6)
        .attr('fill', '#f9fafb')
        .attr('stroke', '#d1d5db');
      this.svg.append('text')
        .attr('x', caja.x + 8)
        .attr('y', caja.y + 14)
        .attr('fill', '#6b7280')
        .attr('font-size', 9)
        .text('San Andrés');
      const pathIslas = geoPath(
        geoMercator().fitExtent(
          [[caja.x + 10, caja.y + 18], [caja.x + caja.w - 10, caja.y + caja.h - 8]],
          islas as any
        )
      );
      pintar(islas.features, pathIslas);
    }

    this.lastSize = sizeKey;
  }

  private codigo(feat: any): string {
    const c = feat?.properties?.DPTO_CCDGO ?? '';
    return String(c).padStart(2, '0');
  }
}
