import { UuidDisplay } from '../components/UuidDisplay';

export default function AppDetail() {
  // Em produção viria dos params/props
  const appId = '00000000-0000-0000-0000-000000000000';

  return (
    <div className="p-8 text-white">
      <h1 className="text-2xl font-bold mb-4">Detalhes do App</h1>
      <div className="text-sm text-gray-400">
        App ID: <UuidDisplay value={appId} />
      </div>
    </div>
  );
}
