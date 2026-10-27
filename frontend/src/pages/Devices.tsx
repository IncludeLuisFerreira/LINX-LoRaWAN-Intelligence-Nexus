import { UuidDisplay } from '../components/UuidDisplay';

export default function Devices() {
  // Em produção viria dos dados da API
  const deviceId = '11111111-1111-1111-1111-111111111111';

  return (
    <div className="p-8 text-white">
      <h1 className="text-2xl font-bold mb-4">Página de Dispositivos</h1>
      <div className="text-sm text-gray-400">
        Device ID: <UuidDisplay value={deviceId} />
      </div>
    </div>
  );
}
