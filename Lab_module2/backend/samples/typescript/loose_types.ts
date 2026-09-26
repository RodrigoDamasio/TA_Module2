// Fetches a user profile and formats it for display.
export async function loadProfile(id: any): Promise<any> {
  const response = await fetch("/api/users/" + id);
  const data: any = await response.json();
  return data;
}

export function displayName(user: any): string {
  return user.firstName + " " + user.lastName;
}

export function formatAge(user: any) {
  return (user.age as number).toFixed(0) + " years";
}
