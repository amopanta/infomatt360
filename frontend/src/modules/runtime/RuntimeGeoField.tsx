import { useState } from 'react';

import { buildGeometry, editableCoordinates, isValidCoordinate, minimumPoints } from './geoEngine';
import type { Coordinate, RuntimeGeoValue } from './geoEngine';
import { RuntimeGeoMap } from './RuntimeGeoMap';
import { useI18n } from '../../i18n';

type Props = {
  id: string;
  type: 'GPS' | 'GEOTRACE' | 'GEOSHAPE';
  label: string;
  required: boolean;
  value?: RuntimeGeoValue | null;
  onChange: (value: RuntimeGeoValue | null) => void;
};

export function RuntimeGeoField({ id, type, label, required, value, onChange }: Props) {
  const { t } = useI18n();
  const [latitude, setLatitude] = useState('');
  const [longitude, setLongitude] = useState('');
  const [status, setStatus] = useState('');
  const coordinates = editableCoordinates(value);
  const needed = minimumPoints(type);

  function addCoordinate(nextLongitude: number, nextLatitude: number) {
    if (!isValidCoordinate(nextLongitude, nextLatitude)) {
      setStatus(t('runtime.coordinateOutOfRange'));
      return;
    }
    const next: Coordinate[] = type === 'GPS' ? [[nextLongitude, nextLatitude]] : [...coordinates, [nextLongitude, nextLatitude]];
    onChange(buildGeometry(type, next));
    setStatus(t('runtime.pointCaptured', { count: next.length }));
  }

  function addManual() {
    addCoordinate(Number(longitude), Number(latitude));
  }

  function captureCurrent() {
    if (!navigator.geolocation) {
      setStatus(t('runtime.noGeolocation'));
      return;
    }
    setStatus(t('runtime.queryingLocation'));
    navigator.geolocation.getCurrentPosition(
      (position) => addCoordinate(position.coords.longitude, position.coords.latitude),
      () => setStatus(t('runtime.locationFailed')),
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 5000 },
    );
  }

  function removeLast() {
    onChange(buildGeometry(type, coordinates.slice(0, -1)));
    setStatus(t('runtime.lastPointRemoved'));
  }

  return (
    <fieldset id={id} className="runtime-geo-field">
      <legend>{label}{required ? ' *' : ''}</legend>
      <div className="runtime-geo-inputs">
        <input aria-label={t('runtime.latitude')} type="number" min={-90} max={90} step="any" value={latitude} placeholder={t('runtime.latitude')} onChange={(event) => setLatitude(event.target.value)} />
        <input aria-label={t('runtime.longitude')} type="number" min={-180} max={180} step="any" value={longitude} placeholder={t('runtime.longitude')} onChange={(event) => setLongitude(event.target.value)} />
      </div>
      <RuntimeGeoMap coordinates={coordinates} closed={type === 'GEOSHAPE'} onAddCoordinate={addCoordinate} />
      <div className="runtime-geo-actions">
        <button type="button" onClick={addManual}>{t('runtime.addCoordinate')}</button>
        <button type="button" onClick={captureCurrent}>{t('runtime.useCurrentLocation')}</button>
        <button type="button" disabled={coordinates.length === 0} onClick={removeLast}>{t('runtime.removeLast')}</button>
      </div>
      <small>{t('runtime.pointsCount', { count: coordinates.length, needed })}</small>
      {coordinates.map(([lon, lat], index) => <code key={`${lon}-${lat}-${index}`}>{index + 1}: {lat.toFixed(6)}, {lon.toFixed(6)}</code>)}
      {status ? <small role="status">{status}</small> : null}
    </fieldset>
  );
}
