import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface CoberturaTerritorial {
  total: number;
  por_codigo: number;
  por_nombre: number;
  sin_departamento: number;
}

export interface DepartamentoTerritorial {
  codigo_dane: string;
  nombre_departamento: string;
  poblacion_total: number | null;
  total_hombres: number | null;
  total_mujeres: number | null;
  n_contratos_por_codigo: number;
  n_contratos_por_nombre: number;
  n_contratos: number;
  valor_total: number | null;
  contratos_por_100k: number | null;
  valor_por_habitante: number | null;
}

export interface TerritorialResponse {
  periodo: string;
  anio_poblacion: number;
  nota: string;
  cobertura: CoberturaTerritorial;
  departamentos: DepartamentoTerritorial[];
}

@Injectable({ providedIn: 'root' })
export class TerritorialService {
  private url = '/api/territorial/departamentos';

  constructor(private http: HttpClient) {}

  getDepartamentos(): Observable<TerritorialResponse> {
    return this.http.get<TerritorialResponse>(this.url);
  }
}
