interface User {
  id: number;
  name: string;
  email?: string;
}

class UserService {
  private users: User[] = [];

  constructor() {
    this.users = [];
  }

  async getUserById(id: number): Promise<User | null> {
    return this.users.find((user) => user.id === id) || null;
  }

  addUser(user: User): void {
    this.users.push(user);
  }
}

function createUser(name: string, id: number, email?: string): User {
  return {
    id,
    name,
    email,
  };
}

const arrowFunction = (x: number, y: number): number => {
  return x + y;
};

enum Status {
  ACTIVE = "active",
  INACTIVE = "inactive",
  PENDING = "pending",
}

type UserWithStatus = User & {
  status: Status;
};

export { createUser, Status, User, UserService, UserWithStatus };
