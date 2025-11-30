<script>
  export let title;
  export let value;
  export let icon;
  export let color = 'blue';
  
  const colorClasses = {
    blue: 'bg-blue-50 text-blue-600',
    green: 'bg-green-50 text-green-600',
    yellow: 'bg-yellow-50 text-yellow-600',
    purple: 'bg-purple-50 text-purple-600',
    red: 'bg-red-50 text-red-600'
  };
</script>

<div class="bg-white rounded-lg shadow-lg p-6">
  <div class="flex items-center justify-between">
    <div>
      <p class="text-sm font-medium text-gray-600 mb-1">{title}</p>
      <p class="text-3xl font-bold text-gray-900">{value}</p>
    </div>
    <div class="text-4xl {colorClasses[color]} w-16 h-16 rounded-full flex items-center justify-center">
      {icon}
    </div>
  </div>
</div>
