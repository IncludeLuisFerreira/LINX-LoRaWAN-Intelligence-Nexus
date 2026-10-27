import { useParams } from 'react-router-dom';
import { UuidDisplay } from '../components/UuidDisplay';

export default function AppDetail() {
  const { app_id, id } = useParams();
  const appId = app_id || id || '00000000-0000-0000-0000-000000000000';

  return (
    <div className="p-8 text-white">
      <h1 className="text-2xl font-bold mb-4">Detalhes do App</h1>
      <div className="text-sm text-gray-400">
        App ID: <UuidDisplay value={appId} />
      </div>
    </div>
  );
}
