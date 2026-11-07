module.exports = {

  INVESTMENT_CITY: {
    description: 'Comparación de inversión por municipio',
    visualization: {
      type: 'bar',
      x: 'city',
      y: 'value',
      title: 'Valor de contratos por municipio (COP)'
    },
    mapRow: r => ({
      city: r.nombre_municipio,
      value: Number(r.total_invertido)
    })
  },

  EXECUTION_TIME_ENTITY: {
    description: 'Duración promedio de ejecución por entidad',
    visualization: {
      type: 'bar',
      x: 'entity',
      y: 'days',
      title: 'Duración promedio de contratos por entidad (días)'
    },
    mapRow: r => ({
      entity: r.entidad,
      days: Number(r.duracion_promedio)
    })
  },

  LONGEST_CONTRACTS: {
    description: 'Contratos con mayor duración',
    visualization: null,
    mapRow: r => r
  },

  RISK_ANALYSIS: {
    description: 'Atipicidad Isolation Forest por departamento (no es irregularidad)',
    visualization: {
      type: 'bar',
      x: 'department',
      y: 'risk',
      title: 'Score IF medio por departamento (mayor = más atípico)'
    },
    mapRow: r => ({
      department: r.nombre_departamento,
      risk: Number(r.riesgo_promedio)
    })
  },

  TOP_PROVIDERS: {
    description: 'Proveedores con más contratos',
    visualization: {
      type: 'bar',
      x: 'proveedor',
      y: 'num_contratos',
      title: 'Número de contratos por proveedor'
    },
    mapRow: r => ({
      proveedor: r.proveedor,
      num_contratos: Number(r.num_contratos),
      total_contratado: Number(r.total_contratado)
    })
  },

  TOP1_IF: {
    description: 'Top 1 % Isolation Forest (c1_if_v1)',
    visualization: {
      type: 'bar',
      x: 'id_contrato',
      y: 'score',
      indexAxis: 'y',
      title: 'Score Isolation Forest (mayor = más atípico)'
    },
    mapRow: r => ({
      rank: Number(r.rank_if),
      id_contrato: r.id_contrato,
      entidad: r.nombre_entidad,
      score: Number(r.score_if)
    })
  },

  BOGOTA_CONTRATACION: {
    description: 'Contratación con sede de la entidad en Bogotá',
    visualization: null,
    mapRow: r => ({
      n: Number(r.n)
    })
  },

  TOP_ENTIDADES: {
    description: 'Entidades contratantes con mayor valor',
    visualization: {
      type: 'bar',
      x: 'entidad',
      y: 'total_contratado',
      indexAxis: 'y',
      title: 'Valor contratado por entidad (COP)'
    },
    mapRow: r => ({
      entidad: String(r.entidad || '').slice(0, 50),
      total_contratado: Number(r.total_contratado)
    })
  },

  MODALIDADES: {
    description: 'Modalidades de contratación',
    visualization: {
      type: 'bar',
      x: 'modalidad',
      y: 'n',
      indexAxis: 'y',
      title: 'Número de contratos por modalidad'
    },
    mapRow: r => ({
      modalidad: r.modalidad,
      n: Number(r.n),
      pct: Number(r.pct)
    })
  },

  PORQUE_ATIPICO: {
    description: 'Qué significa un contrato atípico en C1 + Isolation Forest',
    visualization: null,
    mapRow: r => r
  },

  MAPA_TERRITORIAL: {
    description: 'Mapa temático por departamento (SECOP II y DANE)',
    visualization: {
      type: 'mapa_territorial'
    }
  }

};
