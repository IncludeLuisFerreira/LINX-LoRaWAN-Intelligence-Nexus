export default function Spinner() {
  return (
    <div className="flex h-screen w-full items-center justify-center bg-slate-900">
      <div className="h-10 w-10 animate-spin rounded-full border-4 border-blue-500 border-t-transparent"></div>
    </div>
  );
}
