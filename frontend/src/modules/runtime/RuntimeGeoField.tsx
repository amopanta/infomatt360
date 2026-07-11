import { useState } from 'react';

import { buildGeometry, editableCoordinates, isValidCoordinate, minimumPoints } from './geoEngine';
import type { Coordinate, RuntimeGeoValue } from './geoEngine';
import { RuntimeGeoMap } from './RuntimeGeoMap';

type Props = {
  id: string;
  type: 'GPS' | 'GEOTRACE' | 'GEOSHAPE';
  label: string;
  required: boolean;
  value?: RuntimeGeoValue | null;
  onChange: (value: RuntimeGeoValue | null) => void;
};

export function RuntimeGeoField({ id, type, label, required, value, onChange }: Props) {
  const [latitude, setLatitude] = useState('');
  const [longitude, setLongitude] = useState('');
  const [status, setStatus] = useState('');
  const coordinates = editableCoordinates(value);
  const needed = minimumPoints(type);

  function addCoordinate(nextLongitude: number, nextLatitude: number) {
    if (!isValidCoordinate(nextLongitude, nextLatitude)) {
      setStatus('Coordenada fuera de rango.');
      return;
    }
    const next: Coordinate[] = type === 'GPS' ? [[nextLongitude, nextLatitude]] : [...coordinates, [nextLongitude, nextLatitude]];
    onChange(buildGeometry(type, next));
    setStatus(`Punto ${next.length} capturado.`);
  }

  function addManual() {
    addCoordinate(Number(longitude), Number(latitude));
  }

  function captureCurrent() {
    if (!navigator.geolocation) {
      setStatus('El dispositivo no ofrece geolocalizacion.');
      return;
    }
    setStatus('Consultando ubicacion...');
    navigator.geolocation.getCurrentPosition(
      (position) => addCoordinate(position.coords.longitude, position.coords.latitude),
      () => setStatus('No fue posible obtener la ubicacion.'),
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 5000 },
    );
  }

  function removeLast() {
    onChange(buildGeometry(type, coordinates.slice(0, -1)));
    setStatus('Ultimo punto eliminado.');
  }

  return (
    <fieldset id={id} className="runtime-geo-field">
      <legend>{label}{required ? ' *' : ''}</legend>
      <div className="runtime-geo-inputs">
        <input aria-label="Latitud" type="number" min={-90} max={90} step="any" value={latitude} placeholder="Latitud" onChange={(event) => setLatitude(event.target.value)} />
        <input aria-label="Longitud" type="number" min={-180} max={180} step="any" value={longitude} placeholder="Longitud" onChange={(event) => setLongitude(event.target.value)} />
      </div>
      <RuntimeGeoMap coordinates={coordinates} closed={type === 'GEOSHAPE'} onAddCoordinate={addCoordinate} />
      <div className="runtime-geo-actions">
        <button type="button" onClick={addManual}>Agregar coordenada</button>
        <button type="button" onClick={captureCurrent}>Usar ubicacion actual</button>
        <button type="button" disabled={coordinates.length === 0} onClick={removeLast}>Quitar ultimo</button>
      </div>
      <small>{coordinates.length} punto(s). Minimo recomendado: {needed}.</small>
      {coordinates.map(([lon, lat], index) => <code key={`${lon}-${lat}-${index}`}>{index + 1}: {lat.toFixed(6)}, {lon.toFixed(6)}</code>)}
      {status ? <small role="status">{status}</small> : null}
    </fieldset>
  );
}
