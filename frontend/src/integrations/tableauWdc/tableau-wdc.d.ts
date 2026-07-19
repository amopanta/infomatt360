// La API JS de Tableau (Web Data Connector) no publica un paquete npm ni
// tipos oficiales -- se carga por CDN en tableau-wdc/index.html
// (tableauwdc-2.3.latest.js) y queda disponible como global `tableau`.
// Se declara `any` a proposito en vez de inventar tipos que no podemos
// verificar contra la fuente real.
declare const tableau: any;
